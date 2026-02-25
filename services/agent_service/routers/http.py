import requests
from typing import Optional
from fastapi import APIRouter
from libs.log.tracing import now_ms, mk_trace, new_id
from ..core.orchestrator import simple_plan

router = APIRouter()

VEHICLE_URL = "http://127.0.0.1:8003"
NAV_URL = "http://127.0.0.1:8005"

def env(source: str, typ: str, session_id: str, trace: Optional[dict], payload: dict):
    return {
        "meta": {
            "message_id": new_id("m_"),
            "timestamp_ms": now_ms(),
            "source": source,
            "type": typ,
            "session_id": session_id,
            "trace": mk_trace(trace),
        },
        "payload": payload
    }

@router.get("/health")
def health():
    return {"ok": True}

@router.post("/chat")
def chat(req: dict):
    meta = req.get("meta", {})
    session_id = meta.get("session_id", "demo")
    trace = meta.get("trace")
    utter = req.get("payload") or {}
    text = utter.get("text", "")

    plan = simple_plan(text)

    if plan["type"] == "message":
        return env("agent", "agent.out", session_id, trace, plan["message"])

    tool_call = plan["tool_call"]
    tool_name = tool_call["tool_name"]

    if tool_name.startswith("vehicle."):
        cmd_payload = tool_call["arguments"]
        print("!!!!!!!!!!!!!!!!![agent->vehicle] cmd_payload=", cmd_payload, flush=True)
        try:
            r = requests.post(
                f"{VEHICLE_URL}/command",
                json=env("agent", "vehicle.command", session_id, trace, cmd_payload),
                timeout=3
            )
        except Exception as e:
            return env("agent", "agent.out", session_id, trace, {
                "text": f"[debug] 车控请求异常: {type(e).__name__}: {e}",
                "output_modality": "voice",
                "should_tts": True
            })

        if r.status_code != 200:
            return env("agent", "agent.out", session_id, trace, {
                "text": f"[debug] 车控HTTP失败: {r.status_code}, body={r.text[:200]}",
                "output_modality": "voice",
                "should_tts": True
            })

        data = r.json()
        v = data.get("payload") or {}
        event = v.get("event")
        err = v.get("error")
        state = v.get("state") or {}
        windows = state.get("windows")

        if err or event == "command_rejected":
            return env("agent", "agent.out", session_id, trace, {
                "text": f"[debug] 车控失败: event={event}, error={err}, windows={windows}",
                "output_modality": "voice",
                "should_tts": True
            })

        return env("agent", "agent.out", session_id, trace, {
            "text": f"[debug] 车控成功: event={event}, windows={windows}",
            "output_modality": "voice",
            "should_tts": True
        })

    if tool_name.startswith("nav."):
        return env("agent", "agent.out", session_id, trace, {
            "text": "[debug] nav tool stub",
            "output_modality": "voice",
            "should_tts": True
        })

    return env("agent", "agent.out", session_id, trace, {
        "text": "[debug] unsupported tool",
        "output_modality": "voice",
        "should_tts": True
    })
