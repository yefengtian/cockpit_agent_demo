import json
import os
import shlex
import select
import subprocess
import time
from typing import Any, Dict, List, Optional, Tuple

from libs.config import get_setting

class MCPError(RuntimeError):
    pass


def _extract_json_from_content(content: List[Dict[str, Any]]) -> Dict[str, Any]:
    for item in content:
        if isinstance(item, dict) and item.get("type") == "json" and isinstance(item.get("json"), dict):
            return item["json"]
    for item in content:
        if isinstance(item, dict) and item.get("type") == "text":
            text = item.get("text", "")
            if isinstance(text, str) and text.strip():
                try:
                    obj = json.loads(text)
                    if isinstance(obj, dict):
                        return obj
                except Exception:
                    continue
    return {}


class StdioMCPClient:
    def __init__(
        self,
        command: str,
        startup_timeout_s: float = 10.0,
        extra_env: Optional[Dict[str, str]] = None,
        read_timeout_s: float = 8.0,
    ) -> None:
        if not command.strip():
            raise MCPError("empty MCP command")
        self.command = command
        self.startup_timeout_s = startup_timeout_s
        self.extra_env = extra_env or {}
        self.read_timeout_s = read_timeout_s
        self._proc: Optional[subprocess.Popen] = None
        self._request_id = 1

    def _write_frame(self, payload: Dict[str, Any]) -> None:
        assert self._proc and self._proc.stdin
        body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        header = f"Content-Length: {len(body)}\r\n\r\n".encode("ascii")
        self._proc.stdin.write(header + body)
        self._proc.stdin.flush()

    def _read_exact_with_timeout(self, size: int) -> bytes:
        assert self._proc and self._proc.stdout
        out = b""
        deadline = time.time() + self.read_timeout_s
        while len(out) < size:
            remain = deadline - time.time()
            if remain <= 0:
                raise MCPError("MCP read timeout")
            ready, _, _ = select.select([self._proc.stdout], [], [], remain)
            if not ready:
                raise MCPError("MCP read timeout")
            chunk = self._proc.stdout.read(size - len(out))
            if not chunk:
                raise MCPError("MCP server closed stdout")
            out += chunk
        return out

    def _read_frame(self) -> Dict[str, Any]:
        assert self._proc and self._proc.stdout
        # Read headers
        headers = b""
        deadline = time.time() + self.read_timeout_s
        while b"\r\n\r\n" not in headers:
            remain = deadline - time.time()
            if remain <= 0:
                raise MCPError("MCP header read timeout")
            ready, _, _ = select.select([self._proc.stdout], [], [], remain)
            if not ready:
                raise MCPError("MCP header read timeout")
            chunk = self._proc.stdout.read(1)
            if not chunk:
                raise MCPError("MCP server closed stdout")
            headers += chunk
        head, _ = headers.split(b"\r\n\r\n", 1)
        length = 0
        for line in head.decode("utf-8", errors="ignore").split("\r\n"):
            if line.lower().startswith("content-length:"):
                length = int(line.split(":", 1)[1].strip())
                break
        if length <= 0:
            raise MCPError("invalid MCP frame content-length")
        body = self._read_exact_with_timeout(length)
        obj = json.loads(body.decode("utf-8"))
        if not isinstance(obj, dict):
            raise MCPError("invalid MCP response payload")
        return obj

    def _rpc(self, method: str, params: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        req_id = self._request_id
        self._request_id += 1
        payload: Dict[str, Any] = {"jsonrpc": "2.0", "id": req_id, "method": method}
        if params is not None:
            payload["params"] = params
        self._write_frame(payload)

        while True:
            msg = self._read_frame()
            if msg.get("id") != req_id:
                continue
            if "error" in msg:
                raise MCPError(f"{method} error: {msg['error']}")
            result = msg.get("result")
            if not isinstance(result, dict):
                raise MCPError(f"{method} invalid result")
            return result

    def __enter__(self) -> "StdioMCPClient":
        args = shlex.split(self.command)
        proc_env = os.environ.copy()
        proc_env.update(self.extra_env)
        self._proc = subprocess.Popen(
            args,
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL,
            env=proc_env,
        )
        self._rpc("initialize", {
            "protocolVersion": "2024-11-05",
            "capabilities": {},
            "clientInfo": {"name": "cockpit-agent-demo", "version": "0.2.0"},
        })
        self._write_frame({"jsonrpc": "2.0", "method": "notifications/initialized"})
        return self

    def __exit__(self, exc_type, exc, tb) -> None:
        if self._proc and self._proc.poll() is None:
            self._proc.terminate()
            try:
                self._proc.wait(timeout=2)
            except Exception:
                self._proc.kill()
                self._proc.wait(timeout=2)
        self._proc = None

    def list_tools(self) -> List[Dict[str, Any]]:
        result = self._rpc("tools/list", {})
        tools = result.get("tools")
        return tools if isinstance(tools, list) else []

    def call_tool(self, name: str, arguments: Dict[str, Any]) -> Dict[str, Any]:
        result = self._rpc("tools/call", {"name": name, "arguments": arguments})
        return result


class AmapMCPProvider:
    def __init__(self) -> None:
        self.command = str(get_setting("nav.amap_mcp_command", os.getenv("AMAP_MCP_COMMAND", ""))).strip()
        raw_env = get_setting("nav.amap_mcp_env", {})
        self.extra_env = raw_env if isinstance(raw_env, dict) else {}
        self.read_timeout_s = float(get_setting("nav.amap_mcp_timeout_s", 8))

    def enabled(self) -> bool:
        return bool(self.command)

    @staticmethod
    def _pick_tool_name(tools: List[Dict[str, Any]], keywords: Tuple[str, ...]) -> Optional[str]:
        names = [str(t.get("name", "")) for t in tools if isinstance(t, dict)]
        # 1) exact keyword match
        for n in names:
            if n in keywords:
                return n
        # 2) fuzzy contains all tokens
        for n in names:
            low = n.lower()
            if all(k in low for k in keywords):
                return n
        return None

    def search_poi(self, center: Dict[str, Any], query: str, radius_m: int, limit: int) -> Dict[str, Any]:
        if not self.enabled():
            raise MCPError("AMAP_MCP_COMMAND is not configured")

        with StdioMCPClient(
            self.command,
            extra_env={k: str(v) for k, v in self.extra_env.items()},
            read_timeout_s=self.read_timeout_s,
        ) as mcp:
            tools = mcp.list_tools()
            # Common candidate naming across MCP map providers.
            name = self._pick_tool_name(
                tools,
                ("poi", "search"),
            ) or self._pick_tool_name(tools, ("around", "search")) or self._pick_tool_name(tools, ("poi",))
            if not name:
                raise MCPError("no poi search tool found in MCP tools/list")

            lat = float(center.get("lat", 31.23))
            lon = float(center.get("lon", 121.47))
            candidates = [
                {"query": query, "center": center, "radius_m": radius_m, "limit": limit},
                {"keywords": query, "location": f"{lon},{lat}", "radius": radius_m, "page_size": limit},
                {"keyword": query, "location": f"{lon},{lat}", "radius": radius_m, "limit": limit},
            ]
            last_err = None
            result = {}
            for args in candidates:
                try:
                    result = mcp.call_tool(name, args)
                    last_err = None
                    break
                except Exception as e:
                    last_err = e
            if last_err is not None:
                raise MCPError(f"poi call failed: {last_err}")
            content = result.get("content")
            if not isinstance(content, list):
                return {}
            return _extract_json_from_content(content)

    def plan_route(self, origin: Dict[str, Any], destination: Dict[str, Any], mode: str, avoid: List[str]) -> Dict[str, Any]:
        if not self.enabled():
            raise MCPError("AMAP_MCP_COMMAND is not configured")

        with StdioMCPClient(
            self.command,
            extra_env={k: str(v) for k, v in self.extra_env.items()},
            read_timeout_s=self.read_timeout_s,
        ) as mcp:
            tools = mcp.list_tools()
            name = self._pick_tool_name(
                tools,
                ("route", "plan"),
            ) or self._pick_tool_name(tools, ("direction", "driving")) or self._pick_tool_name(tools, ("route",))
            if not name:
                raise MCPError("no route tool found in MCP tools/list")

            o_lat = float(origin.get("lat", 31.23))
            o_lon = float(origin.get("lon", 121.47))
            d_lat = float(destination.get("lat", 31.20))
            d_lon = float(destination.get("lon", 121.44))
            candidates = [
                {"origin": origin, "destination": destination, "mode": mode, "avoid": avoid},
                {"origin": f"{o_lon},{o_lat}", "destination": f"{d_lon},{d_lat}", "strategy": mode},
                {"from": f"{o_lon},{o_lat}", "to": f"{d_lon},{d_lat}", "mode": mode},
            ]
            last_err = None
            result = {}
            for args in candidates:
                try:
                    result = mcp.call_tool(name, args)
                    last_err = None
                    break
                except Exception as e:
                    last_err = e
            if last_err is not None:
                raise MCPError(f"route call failed: {last_err}")
            content = result.get("content")
            if not isinstance(content, list):
                return {}
            return _extract_json_from_content(content)
