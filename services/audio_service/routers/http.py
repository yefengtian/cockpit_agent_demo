from fastapi import APIRouter
from libs.log.tracing import now_ms, mk_trace, new_id

router = APIRouter()

@router.get("/health")
def health():
    return {"ok": True}

@router.post("/tts")
def tts(req: dict):
    # Envelope in -> Envelope out (stub)
    meta = req.get("meta", {})
    out = {
        "meta": {
            "message_id": new_id("m_"),
            "timestamp_ms": now_ms(),
            "source": "audio",
            "type": "audio.tts.audio",
            "session_id": meta.get("session_id", "demo"),
            "trace": mk_trace(meta.get("trace")),
        },
        "payload": {
            "audio_b64": "",  # TODO: generate real audio
            "format": "wav",
            "sample_rate_hz": 16000
        }
    }
    return out