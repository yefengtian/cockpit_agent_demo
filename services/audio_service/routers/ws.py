import json
from fastapi import APIRouter, WebSocket, WebSocketDisconnect
from libs.log.tracing import now_ms, mk_trace, new_id

router = APIRouter()

@router.websocket("/ws/audio")
async def ws_audio(ws: WebSocket):
    await ws.accept()
    try:
        while True:
            raw = await ws.receive_text()
            msg = json.loads(raw)
            meta = msg.get("meta", {})
            payload = msg.get("payload", {})
            # Stub: whenever is_last True -> output final transcript
            if payload.get("is_last") is True:
                out = {
                    "meta": {
                        "message_id": new_id("m_"),
                        "timestamp_ms": now_ms(),
                        "source": "audio",
                        "type": "audio.transcript.final",
                        "session_id": meta.get("session_id", "demo"),
                        "trace": mk_trace(meta.get("trace")),
                    },
                    "payload": {
                        "text": "（stub）我想把副驾窗开到30%",
                        "is_final": True,
                        "language": "zh-CN",
                        "confidence": 0.5,
                        "segments": []
                    }
                }
                await ws.send_text(json.dumps(out, ensure_ascii=False))
    except WebSocketDisconnect:
        return