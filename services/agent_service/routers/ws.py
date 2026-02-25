import json
from fastapi import APIRouter, WebSocket
from libs.log.tracing import now_ms, mk_trace, new_id
from ..core.orchestrator import simple_plan

router = APIRouter()

@router.websocket("/ws/agent")
async def ws_agent(ws: WebSocket):
    await ws.accept()
    while True:
        raw = await ws.receive_text()
        msg = json.loads(raw)
        meta = msg.get("meta", {})
        session_id = meta.get("session_id", "demo")
        trace = meta.get("trace")
        utter = msg.get("payload") or {}
        plan = simple_plan(utter.get("text", ""))

        if plan["type"] == "message":
            out = {
                "meta": {
                    "message_id": new_id("m_"),
                    "timestamp_ms": now_ms(),
                    "source": "agent",
                    "type": "agent.out",
                    "session_id": session_id,
                    "trace": mk_trace(trace),
                },
                "payload": plan["message"]
            }
            await ws.send_text(json.dumps(out, ensure_ascii=False))
        else:
            out = {
                "meta": {
                    "message_id": new_id("m_"),
                    "timestamp_ms": now_ms(),
                    "source": "agent",
                    "type": "agent.tool_call",
                    "session_id": session_id,
                    "trace": mk_trace(trace),
                },
                "payload": plan["tool_call"]
            }
            await ws.send_text(json.dumps(out, ensure_ascii=False))