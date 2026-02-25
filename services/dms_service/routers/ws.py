import asyncio
import json
from fastapi import APIRouter, WebSocket
from libs.log.tracing import now_ms, mk_trace, new_id

router = APIRouter()

@router.websocket("/ws/dms")
async def ws_dms(ws: WebSocket):
    await ws.accept()
    # demo: periodic event
    while True:
        out = {
            "meta": {
                "message_id": new_id("m_"),
                "timestamp_ms": now_ms(),
                "source": "dms",
                "type": "dms.event",
                "session_id": "demo",
                "trace": mk_trace(None),
            },
            "payload": {
                "event_type": "DISTRACTION_GAZE_OFF_ROAD",
                "severity": 3,
                "duration_ms": 1200,
                "metrics": {}
            }
        }
        await ws.send_text(json.dumps(out, ensure_ascii=False))
        await asyncio.sleep(5)