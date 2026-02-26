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
        transport: str = "content_length",
    ) -> None:
        if not command.strip():
            raise MCPError("empty MCP command")
        self.command = command
        self.startup_timeout_s = startup_timeout_s
        self.extra_env = extra_env or {}
        self.read_timeout_s = read_timeout_s
        self.transport = transport
        self._proc: Optional[subprocess.Popen] = None
        self._request_id = 1
        self._stdout_buf = b""

    def _stderr_hint(self) -> str:
        if not self._proc or not self._proc.stderr:
            return ""
        try:
            ready, _, _ = select.select([self._proc.stderr], [], [], 0)
            if not ready:
                return ""
            data = os.read(self._proc.stderr.fileno(), 4096)
            if not data:
                return ""
            text = bytes(data).decode("utf-8", errors="ignore").strip()
            return text[-400:] if text else ""
        except Exception:
            return ""

    def _write_frame(self, payload: Dict[str, Any]) -> None:
        assert self._proc and self._proc.stdin
        body = json.dumps(payload, ensure_ascii=False)
        if self.transport == "ndjson":
            self._proc.stdin.write((body + "\n").encode("utf-8"))
            self._proc.stdin.flush()
            return
        body_b = body.encode("utf-8")
        header = f"Content-Length: {len(body_b)}\r\n\r\n".encode("ascii")
        self._proc.stdin.write(header + body_b)
        self._proc.stdin.flush()

    def _read_exact_with_timeout(self, size: int) -> bytes:
        assert self._proc and self._proc.stdout
        out = b""
        deadline = time.time() + self.read_timeout_s
        while len(out) < size:
            remain = deadline - time.time()
            if remain <= 0:
                hint = self._stderr_hint()
                raise MCPError(f"MCP read timeout{(' | stderr: ' + hint) if hint else ''}")
            ready, _, _ = select.select([self._proc.stdout], [], [], remain)
            if not ready:
                hint = self._stderr_hint()
                raise MCPError(f"MCP read timeout{(' | stderr: ' + hint) if hint else ''}")
            chunk = os.read(self._proc.stdout.fileno(), size - len(out))
            if not chunk:
                raise MCPError("MCP server closed stdout")
            out += chunk
        return out

    def _read_some_stdout(self, timeout_s: float) -> bytes:
        assert self._proc and self._proc.stdout
        ready, _, _ = select.select([self._proc.stdout], [], [], timeout_s)
        if not ready:
            return b""
        try:
            return os.read(self._proc.stdout.fileno(), 4096)
        except BlockingIOError:
            return b""

    def _read_frame(self) -> Dict[str, Any]:
        assert self._proc and self._proc.stdout
        if self.transport == "ndjson":
            deadline = time.time() + self.read_timeout_s
            while True:
                nl = self._stdout_buf.find(b"\n")
                if nl != -1:
                    line = self._stdout_buf[:nl]
                    self._stdout_buf = self._stdout_buf[nl + 1:]
                    raw = line.decode("utf-8", errors="ignore").strip()
                    if not raw:
                        continue
                    obj = json.loads(raw)
                    if not isinstance(obj, dict):
                        raise MCPError("invalid MCP ndjson response payload")
                    return obj
                remain = deadline - time.time()
                if remain <= 0:
                    hint = self._stderr_hint()
                    raise MCPError(f"MCP line read timeout{(' | stderr: ' + hint) if hint else ''}")
                chunk = self._read_some_stdout(remain)
                if not chunk:
                    hint = self._stderr_hint()
                    raise MCPError(f"MCP line read timeout{(' | stderr: ' + hint) if hint else ''}")
                self._stdout_buf += chunk

        # Read headers
        headers = b""
        deadline = time.time() + self.read_timeout_s
        while b"\r\n\r\n" not in headers:
            if self._stdout_buf:
                headers += self._stdout_buf
                self._stdout_buf = b""
                if b"\r\n\r\n" in headers:
                    break
            remain = deadline - time.time()
            if remain <= 0:
                hint = self._stderr_hint()
                raise MCPError(f"MCP header read timeout{(' | stderr: ' + hint) if hint else ''}")
            chunk = self._read_some_stdout(remain)
            if not chunk:
                hint = self._stderr_hint()
                raise MCPError(f"MCP header read timeout{(' | stderr: ' + hint) if hint else ''}")
            headers += chunk
        head, tail = headers.split(b"\r\n\r\n", 1)
        length = 0
        for line in head.decode("utf-8", errors="ignore").split("\r\n"):
            if line.lower().startswith("content-length:"):
                length = int(line.split(":", 1)[1].strip())
                break
        if length <= 0:
            raise MCPError("invalid MCP frame content-length")
        if len(tail) >= length:
            body = tail[:length]
            self._stdout_buf = tail[length:]
        else:
            need = length - len(tail)
            body = tail + self._read_exact_with_timeout(need)
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
            stderr=subprocess.PIPE,
            env=proc_env,
        )
        if self._proc.stdout is not None:
            os.set_blocking(self._proc.stdout.fileno(), False)
        if self._proc.stderr is not None:
            os.set_blocking(self._proc.stderr.fileno(), False)
        self._rpc("initialize", {
            "protocolVersion": "2024-11-05",
            "capabilities": {},
            "clientInfo": {"name": "cockpit-agent-demo", "version": "0.2.0"},
        })
        self._write_frame({"jsonrpc": "2.0", "method": "notifications/initialized", "params": {}})
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
        default_cmd = "npx -y -p @amap/amap-maps-mcp-server mcp-amap"
        self.command = str(get_setting("nav.amap_mcp_command", os.getenv("AMAP_MCP_COMMAND", default_cmd))).strip()
        raw_env = get_setting("nav.amap_mcp_env", {})
        self.extra_env = raw_env if isinstance(raw_env, dict) else {}
        self.read_timeout_s = float(get_setting("nav.amap_mcp_timeout_s", 8))
        self.transport = str(get_setting("nav.amap_mcp_transport", "ndjson")).strip().lower()
        self.total_timeout_s = float(get_setting("nav.amap_mcp_total_timeout_s", 20))

    def _transport_candidates(self) -> List[str]:
        t = self.transport
        if t == "auto":
            return ["ndjson", "content_length"]
        if t == "ndjson":
            return ["ndjson"]
        if t == "content_length":
            return ["content_length"]
        return ["ndjson"]

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

    @staticmethod
    def _to_canonical_poi(data: Dict[str, Any]) -> Dict[str, Any]:
        # Already canonical
        if isinstance(data.get("items"), list):
            return data

        # AMap common shape: {"pois":[{"name","location","address","distance"}]}
        pois = data.get("pois")
        if isinstance(pois, list):
            items = []
            for p in pois:
                if not isinstance(p, dict):
                    continue
                loc = str(p.get("location", "")).strip()
                lon = 0.0
                lat = 0.0
                if "," in loc:
                    try:
                        lon_s, lat_s = loc.split(",", 1)
                        lon = float(lon_s)
                        lat = float(lat_s)
                    except Exception:
                        lon = float(p.get("lon", 0.0) or 0.0)
                        lat = float(p.get("lat", 0.0) or 0.0)
                else:
                    lon = float(p.get("lon", 0.0) or 0.0)
                    lat = float(p.get("lat", 0.0) or 0.0)
                try:
                    distance_m = float(p.get("distance", 0) or 0)
                except Exception:
                    distance_m = 0.0
                items.append({
                    "name": str(p.get("name", "") or "POI"),
                    "lat": lat,
                    "lon": lon,
                    "address": str(p.get("address", "") or ""),
                    "distance_m": distance_m,
                })
            return {"items": items}

        return data

    @staticmethod
    def _to_canonical_route(data: Dict[str, Any]) -> Dict[str, Any]:
        # Already canonical
        if "distance_m" in data and "duration_s" in data:
            return data

        # AMap common shape:
        # {"route":{"paths":[{"distance":"4510","duration":"1258","steps":[{"instruction","distance"}]}]}}
        route = data.get("route")
        if isinstance(route, dict):
            paths = route.get("paths")
            if isinstance(paths, list) and paths:
                p0 = paths[0] if isinstance(paths[0], dict) else {}
                try:
                    distance_m = float(p0.get("distance", 0) or 0)
                except Exception:
                    distance_m = 0.0
                try:
                    duration_s = float(p0.get("duration", 0) or 0)
                except Exception:
                    duration_s = 0.0
                steps_in = p0.get("steps")
                steps_out = []
                if isinstance(steps_in, list):
                    for s in steps_in:
                        if not isinstance(s, dict):
                            continue
                        try:
                            step_dist = float(s.get("distance", 0) or 0)
                        except Exception:
                            step_dist = 0.0
                        steps_out.append({
                            "instruction": str(s.get("instruction", "") or ""),
                            "distance_m": step_dist,
                        })
                return {
                    "distance_m": distance_m,
                    "duration_s": duration_s,
                    "summary": "高德驾车路线",
                    "polyline": str(p0.get("polyline", "") or ""),
                    "steps": steps_out,
                }

        return data

    def search_poi(self, center: Dict[str, Any], query: str, radius_m: int, limit: int) -> Dict[str, Any]:
        if not self.enabled():
            raise MCPError("AMAP_MCP_COMMAND is not configured")

        last_err: Optional[Exception] = None
        start = time.time()
        for transport in self._transport_candidates():
            remaining_total = self.total_timeout_s - (time.time() - start)
            if remaining_total <= 0:
                break
            per_try_timeout = max(1.0, min(self.read_timeout_s, remaining_total))
            try:
                with StdioMCPClient(
                    self.command,
                    extra_env={k: str(v) for k, v in self.extra_env.items()},
                    read_timeout_s=per_try_timeout,
                    transport=transport,
                ) as mcp:
                    tools = mcp.list_tools()
                    # Prefer the exact tool names observed in your smoke test.
                    around_tool = self._pick_tool_name(tools, ("maps_around_search",))
                    text_tool = self._pick_tool_name(tools, ("maps_text_search",))
                    name = around_tool or text_tool or self._pick_tool_name(tools, ("poi", "search")) or self._pick_tool_name(tools, ("around", "search")) or self._pick_tool_name(tools, ("poi",))
                    if not name:
                        raise MCPError("no poi search tool found in MCP tools/list")

                    lat = float(center.get("lat", 31.23))
                    lon = float(center.get("lon", 121.47))
                    if name == "maps_around_search":
                        candidates = [
                            {"keywords": query, "location": f"{lon},{lat}", "radius": radius_m, "page_size": limit},
                            {"keywords": query, "location": f"{lon},{lat}", "radius": radius_m},
                        ]
                    elif name == "maps_text_search":
                        candidates = [
                            {"keywords": query, "city": "全国", "page_size": limit},
                            {"keywords": query},
                        ]
                    else:
                        candidates = [
                            {"query": query, "center": center, "radius_m": radius_m, "limit": limit},
                            {"keywords": query, "location": f"{lon},{lat}", "radius": radius_m, "page_size": limit},
                            {"keyword": query, "location": f"{lon},{lat}", "radius": radius_m, "limit": limit},
                        ]
                    call_err = None
                    result = {}
                    for args in candidates:
                        try:
                            result = mcp.call_tool(name, args)
                            call_err = None
                            break
                        except Exception as e:
                            call_err = e
                    if call_err is not None:
                        raise MCPError(f"poi call failed: {call_err}")
                    content = result.get("content")
                    if not isinstance(content, list):
                        return {}
                    raw = _extract_json_from_content(content)
                    return self._to_canonical_poi(raw)
            except Exception as e:
                last_err = e
                continue
        raise MCPError(f"poi failed on all transports within {self.total_timeout_s}s: {last_err}")

    def plan_route(self, origin: Dict[str, Any], destination: Dict[str, Any], mode: str, avoid: List[str]) -> Dict[str, Any]:
        if not self.enabled():
            raise MCPError("AMAP_MCP_COMMAND is not configured")

        last_err: Optional[Exception] = None
        start = time.time()
        for transport in self._transport_candidates():
            remaining_total = self.total_timeout_s - (time.time() - start)
            if remaining_total <= 0:
                break
            per_try_timeout = max(1.0, min(self.read_timeout_s, remaining_total))
            try:
                with StdioMCPClient(
                    self.command,
                    extra_env={k: str(v) for k, v in self.extra_env.items()},
                    read_timeout_s=per_try_timeout,
                    transport=transport,
                ) as mcp:
                    tools = mcp.list_tools()
                    # Prefer exact known tool name from your smoke test.
                    name = self._pick_tool_name(tools, ("maps_direction_driving",)) or self._pick_tool_name(
                        tools,
                        ("route", "plan"),
                    ) or self._pick_tool_name(tools, ("direction", "driving")) or self._pick_tool_name(tools, ("route",))
                    if not name:
                        raise MCPError("no route tool found in MCP tools/list")

                    o_lat = float(origin.get("lat", 31.23))
                    o_lon = float(origin.get("lon", 121.47))
                    d_lat = float(destination.get("lat", 31.20))
                    d_lon = float(destination.get("lon", 121.44))
                    if name == "maps_direction_driving":
                        candidates = [
                            {"origin": f"{o_lon},{o_lat}", "destination": f"{d_lon},{d_lat}"},
                            {"origin": f"{o_lon},{o_lat}", "destination": f"{d_lon},{d_lat}", "strategy": 0},
                        ]
                    else:
                        candidates = [
                            {"origin": origin, "destination": destination, "mode": mode, "avoid": avoid},
                            {"origin": f"{o_lon},{o_lat}", "destination": f"{d_lon},{d_lat}", "strategy": mode},
                            {"from": f"{o_lon},{o_lat}", "to": f"{d_lon},{d_lat}", "mode": mode},
                        ]
                    call_err = None
                    result = {}
                    for args in candidates:
                        try:
                            result = mcp.call_tool(name, args)
                            call_err = None
                            break
                        except Exception as e:
                            call_err = e
                    if call_err is not None:
                        raise MCPError(f"route call failed: {call_err}")
                    content = result.get("content")
                    if not isinstance(content, list):
                        return {}
                    raw = _extract_json_from_content(content)
                    return self._to_canonical_route(raw)
            except Exception as e:
                last_err = e
                continue
        raise MCPError(f"route failed on all transports within {self.total_timeout_s}s: {last_err}")
