import re
from libs.log.tracing import new_id

def simple_plan(text: str) -> dict:
    """
    Return either:
      {"type": "tool_call", "tool_call": {...}}
      {"type": "message", "message": {...}}
    """
    t = text.strip()

    # window: "副驾窗开到30%"
    m = re.search(r"(副驾|副驾驶|右前).*(窗).*(\d{1,3})\s*%", t)
    if m:
        pct = int(m.group(3))
        pct = max(0, min(100, pct))
        return {
            "type": "tool_call",
            "tool_call": {
                "tool_name": "vehicle.control",
                "call_id": new_id("call_"),
                "arguments": {"command": "set_window", "args": {"position": "FR", "percent": pct}},
                "requires_confirmation": False
            }
        }

    # ac temp: "温度调到24"
    m = re.search(r"(温度).*(\d{2})", t)
    if m:
        temp = float(m.group(2))
        temp = max(16.0, min(30.0, temp))
        return {
            "type": "tool_call",
            "tool_call": {
                "tool_name": "vehicle.control",
                "call_id": new_id("call_"),
                "arguments": {"command": "set_ac", "args": {"temp_c": temp, "ac_on": True}},
                "requires_confirmation": False
            }
        }

    # nav: "最近的星巴克"
    if "星巴克" in t or "充电站" in t:
        return {
            "type": "tool_call",
            "tool_call": {
                "tool_name": "nav.poi",
                "call_id": new_id("call_"),
                "arguments": {"center": {"lat": 31.23, "lon": 121.47}, "query": "Starbucks", "radius_m": 5000, "limit": 3},
                "requires_confirmation": False
            }
        }

    return {
        "type": "message",
        "message": {"text": "我在。你可以说：把副驾窗开到30%、温度调到24、带我去最近的星巴克。", "output_modality": "voice", "should_tts": True}
    }