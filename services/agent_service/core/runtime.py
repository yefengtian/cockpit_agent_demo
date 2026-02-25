from typing import Any, Dict, Optional

import requests

from libs.log.tracing import mk_trace, new_id, now_ms
from libs.schema_utils.validate import SchemaValidationError, validate_or_raise
from .orchestrator import simple_plan

VEHICLE_URL = "http://127.0.0.1:8003"
NAV_URL = "http://127.0.0.1:8005"


def env(source: str, typ: str, session_id: str, trace: Optional[dict], payload: dict) -> dict:
    return {
        "meta": {
            "message_id": new_id("m_"),
            "timestamp_ms": now_ms(),
            "source": source,
            "type": typ,
            "session_id": session_id,
            "trace": mk_trace(trace),
        },
        "payload": payload,
    }


def _safe_json(resp: requests.Response) -> Dict[str, Any]:
    try:
        data = resp.json()
        return data if isinstance(data, dict) else {}
    except Exception:
        return {}


def _agent_out(session_id: str, trace: Optional[dict], text: str) -> dict:
    out = env("agent", "agent.out", session_id, trace, {
        "text": text,
        "output_modality": "voice",
        "should_tts": True,
    })
    validate_or_raise("schemas/common/envelope.schema.json", out)
    return out


def execute_text_plan(session_id: str, trace: Optional[dict], text: str) -> dict:
    plan = simple_plan(text)
    if plan["type"] == "message":
        out = env("agent", "agent.out", session_id, trace, plan["message"])
        validate_or_raise("schemas/common/envelope.schema.json", out)
        return out

    tool_call = plan["tool_call"]
    tool_name = tool_call["tool_name"]

    if tool_name.startswith("vehicle."):
        cmd_payload = tool_call["arguments"]
        try:
            validate_or_raise("schemas/vehicle/vehicle_command.schema.json", cmd_payload)
        except SchemaValidationError as e:
            return _agent_out(session_id, trace, f"车控参数不合法: {e}")

        try:
            r = requests.post(
                f"{VEHICLE_URL}/command",
                json=env("agent", "vehicle.command", session_id, trace, cmd_payload),
                timeout=3,
            )
        except Exception as e:
            return _agent_out(session_id, trace, f"车控请求异常: {type(e).__name__}: {e}")

        data = _safe_json(r)
        payload = data.get("payload") or {}
        event = payload.get("event")
        err = payload.get("error")
        windows = (payload.get("state") or {}).get("windows")
        if r.status_code != 200 or err or event == "command_rejected":
            return _agent_out(session_id, trace, f"车控失败: event={event}, error={err}, windows={windows}")
        return _agent_out(session_id, trace, f"车控成功: event={event}, windows={windows}")

    if tool_name == "nav.poi":
        try:
            r = requests.post(
                f"{NAV_URL}/poi",
                json=env("agent", "nav.poi.request", session_id, trace, tool_call["arguments"]),
                timeout=3,
            )
        except Exception as e:
            return _agent_out(session_id, trace, f"导航请求异常: {type(e).__name__}: {e}")

        data = _safe_json(r)
        items = ((data.get("payload") or {}).get("items")) or []
        if r.status_code != 200 or not items:
            return _agent_out(session_id, trace, "未找到合适地点，请换个关键词试试。")
        first = items[0]
        name = first.get("name", "目标地点")
        distance_m = int(first.get("distance_m", 0))
        return _agent_out(session_id, trace, f"已找到最近的{name}，距离约{distance_m}米。")

    if tool_name == "nav.route":
        try:
            r = requests.post(
                f"{NAV_URL}/route",
                json=env("agent", "nav.route.request", session_id, trace, tool_call["arguments"]),
                timeout=3,
            )
        except Exception as e:
            return _agent_out(session_id, trace, f"算路请求异常: {type(e).__name__}: {e}")
        data = _safe_json(r)
        payload = data.get("payload") or {}
        summary = payload.get("summary", "推荐路线")
        distance_m = int(payload.get("distance_m", 0))
        if r.status_code != 200:
            return _agent_out(session_id, trace, "算路失败，请稍后再试。")
        return _agent_out(session_id, trace, f"{summary}，全程约{distance_m}米。")

    return _agent_out(session_id, trace, f"暂不支持工具: {tool_name}")
