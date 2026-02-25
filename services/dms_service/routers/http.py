from typing import Optional
from fastapi import APIRouter
from libs.log.tracing import now_ms, mk_trace, new_id

router = APIRouter()

def envelope(typ: str, session_id: str, trace: Optional[dict], payload: dict):
    return {
        "meta": {
            "message_id": new_id("m_"),
            "timestamp_ms": now_ms(),
            "source": "dms",
            "type": typ,
            "session_id": session_id,
            "trace": mk_trace(trace),
        },
        "payload": payload
    }

@router.get("/health")
def health():
    return {"ok": True}

@router.post("/frame")
def frame(req: dict):
    meta = req.get("meta", {})
    session_id = meta.get("session_id", "demo")
    trace = meta.get("trace")
    # stub: always no-face
    return envelope("dms.event", session_id, trace, {
        "event_type": "NO_FACE",
        "severity": 2,
        "duration_ms": 0,
        "metrics": {}
    })