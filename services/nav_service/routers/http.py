from typing import Optional
from fastapi import APIRouter
from libs.log.tracing import now_ms, mk_trace, new_id

router = APIRouter()

def envelope(typ: str, session_id: str, trace: Optional[dict], payload: dict):
    return {
        "meta": {
            "message_id": new_id("m_"),
            "timestamp_ms": now_ms(),
            "source": "nav",
            "type": typ,
            "session_id": session_id,
            "trace": mk_trace(trace),
        },
        "payload": payload
    }

@router.get("/health")
def health():
    return {"ok": True}

@router.post("/route")
def route(req: dict):
    meta = req.get("meta", {})
    session_id = meta.get("session_id", "demo")
    trace = meta.get("trace")
    # stub result
    return envelope("nav.route.result", session_id, trace, {
        "distance_m": 5200,
        "duration_s": 780,
        "summary": "（stub）推荐路线",
        "polyline": "",
        "steps": [{"instruction": "直行 1 公里", "distance_m": 1000}]
    })

@router.post("/poi")
def poi(req: dict):
    meta = req.get("meta", {})
    session_id = meta.get("session_id", "demo")
    trace = meta.get("trace")
    return envelope("nav.poi.result", session_id, trace, {
        "items": [
            {"name": "（stub）Starbucks", "lat": 31.23, "lon": 121.47, "address": "Somewhere", "distance_m": 850}
        ]
    })