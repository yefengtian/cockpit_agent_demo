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
