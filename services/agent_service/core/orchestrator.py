import re
from typing import Any, Dict, Optional

from libs.log.tracing import new_id
from .llm import LLMError, OpenAICompatLLM, build_planner_messages

_LLM = OpenAICompatLLM()


def _mk_tool(tool_name: str, arguments: Dict[str, Any], requires_confirmation: bool = False) -> Dict[str, Any]:
    return {
        "type": "tool_call",
        "tool_call": {
            "tool_name": tool_name,
            "call_id": new_id("call_"),
            "arguments": arguments,
            "requires_confirmation": requires_confirmation,
        },
    }


def _mk_msg(text: str) -> Dict[str, Any]:
    return {
        "type": "message",
        "message": {"text": text, "output_modality": "voice", "should_tts": True},
    }


def _rule_fallback(text: str) -> Dict[str, Any]:
    t = text.strip()
    m = re.search(r"(副驾|副驾驶|右前).*?(窗).*?(\d{1,3})\s*[%％]", t)
    if m:
        pct = max(0, min(100, int(m.group(3))))
        return _mk_tool("vehicle.control", {"command": "set_window", "args": {"position": "FR", "percent": pct}})

    m = re.search(r"(主驾|左前).*?(窗).*?(\d{1,3})\s*[%％]", t)
    if m:
        pct = max(0, min(100, int(m.group(3))))
        return _mk_tool("vehicle.control", {"command": "set_window", "args": {"position": "FL", "percent": pct}})

    m = re.search(r"(温度).*(\d{2})", t)
    if m:
        temp = max(16.0, min(30.0, float(m.group(2))))
        return _mk_tool("vehicle.control", {"command": "set_ac", "args": {"temp_c": temp, "ac_on": True}})

    if "星巴克" in t:
        return _mk_tool("nav.poi", {"center": {"lat": 31.23, "lon": 121.47}, "query": "星巴克", "radius_m": 5000, "limit": 3})
    if "充电站" in t:
        return _mk_tool("nav.poi", {"center": {"lat": 31.23, "lon": 121.47}, "query": "充电站", "radius_m": 5000, "limit": 5})

    return _mk_msg("我在。你可以直接说你的需求，比如调空调、开车窗、找附近地点或规划路线。")


def _normalize_llm_plan(raw: Dict[str, Any]) -> Dict[str, Any]:
    def _coerce_int(v: Any, default: int = 0) -> int:
        try:
            return int(float(v))
        except Exception:
            return default

    def _coerce_float(v: Any, default: float = 24.0) -> float:
        try:
            return float(v)
        except Exception:
            return default

    def _norm_window_position(v: Any) -> str:
        s = str(v or "").strip().upper()
        if s in {"FL", "FR", "RL", "RR"}:
            return s
        mapping = {
            "LF": "FL",
            "RF": "FR",
            "LR": "RL",
            "RRR": "RR",
            "LEFT_FRONT": "FL",
            "RIGHT_FRONT": "FR",
            "LEFT_REAR": "RL",
            "RIGHT_REAR": "RR",
            "主驾": "FL",
            "左前": "FL",
            "副驾": "FR",
            "副驾驶": "FR",
            "右前": "FR",
            "左后": "RL",
            "右后": "RR",
        }
        return mapping.get(s, "FR")

    def _normalize_vehicle_arguments(arguments: Dict[str, Any]) -> Dict[str, Any]:
        # Accept several LLM output styles:
        # 1) {"command":"set_window","args":{...}}
        # 2) {"action":"set_window", ...}
        # 3) {"vehicle_command": {...}}
        src = arguments
        if isinstance(arguments.get("vehicle_command"), dict):
            src = arguments["vehicle_command"]

        cmd = str(src.get("command") or src.get("action") or src.get("cmd") or "").strip().lower()
        cmd_alias = {
            "window": "set_window",
            "setwindow": "set_window",
            "set_window_percent": "set_window",
            "window_adjust": "set_window",
            "ac": "set_ac",
            "set_temp": "set_ac",
            "set_temperature": "set_ac",
            "fan": "set_fan_speed",
            "set_fan": "set_fan_speed",
            "ac_mode": "set_ac_mode",
            "set_mode": "set_ac_mode",
            "recirc": "set_recirc",
            "set_recirculation": "set_recirc",
            "state": "get_state",
            "getstate": "get_state",
        }
        cmd = cmd_alias.get(cmd, cmd)

        raw_args = src.get("args")
        if not isinstance(raw_args, dict):
            raw_args = src if isinstance(src, dict) else {}

        if cmd == "set_window":
            pos = raw_args.get("position", raw_args.get("window", raw_args.get("seat", "FR")))
            pct = raw_args.get("percent", raw_args.get("pct", raw_args.get("value", raw_args.get("open_percent", raw_args.get("level", 0)))))
            return {"command": "set_window", "args": {"position": _norm_window_position(pos), "percent": max(0, min(100, _coerce_int(pct, 0)))}}
        if cmd == "set_ac":
            temp = raw_args.get("temp_c", raw_args.get("temperature", raw_args.get("temp", 24)))
            on = raw_args.get("ac_on", raw_args.get("on", raw_args.get("enable", True)))
            return {"command": "set_ac", "args": {"temp_c": max(16.0, min(30.0, _coerce_float(temp, 24.0))), "ac_on": bool(on)}}
        if cmd == "set_fan_speed":
            lvl = raw_args.get("level", raw_args.get("fan_level", raw_args.get("speed", 2)))
            return {"command": "set_fan_speed", "args": {"level": max(1, min(7, _coerce_int(lvl, 2)))}}
        if cmd == "set_ac_mode":
            mode = str(raw_args.get("mode", "auto")).strip().lower()
            mode_alias = {"front": "face", "windshield": "defrost"}
            mode = mode_alias.get(mode, mode)
            if mode not in {"face", "feet", "defrost", "auto"}:
                mode = "auto"
            return {"command": "set_ac_mode", "args": {"mode": mode}}
        if cmd == "set_recirc":
            ro = raw_args.get("recirc_on", raw_args.get("on", False))
            return {"command": "set_recirc", "args": {"recirc_on": bool(ro)}}
        if cmd == "get_state":
            return {"command": "get_state", "args": {}}
        return {"command": "get_state", "args": {}}

    if raw.get("type") == "message":
        m = raw.get("message") or {}
        text = str(m.get("text", "")).strip() or "好的，我在。请告诉我你的需求。"
        return _mk_msg(text)
    if raw.get("type") == "tool_call":
        tool_name = str(raw.get("tool_name", "")).strip()
        arguments = raw.get("arguments")
        if not isinstance(arguments, dict):
            arguments = {}
        if tool_name in {"vehicle.control", "nav.poi", "nav.route"}:
            if tool_name == "vehicle.control":
                arguments = _normalize_vehicle_arguments(arguments)
            return _mk_tool(tool_name, arguments, bool(raw.get("requires_confirmation", False)))
    return _mk_msg("我收到了，但还不够明确。请再具体一点，比如目标地点或车控参数。")

def simple_plan(text: str, speaker: Optional[str] = None, language: Optional[str] = None) -> dict:
    t = str(text or "").strip()
    if not t:
        return _mk_msg("我在。请告诉我你想做什么。")

    try:
        messages = build_planner_messages(t, speaker=speaker, language=language)
        raw = _LLM.chat_json(messages=messages, temperature=0.1)
        return _normalize_llm_plan(raw)
    except LLMError:
        return _rule_fallback(t)
