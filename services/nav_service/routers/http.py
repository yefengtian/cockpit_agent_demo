from typing import Optional
from fastapi import APIRouter
from libs.log.tracing import now_ms, mk_trace, new_id
from libs.schema_utils.validate import SchemaValidationError, validate_or_raise

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
    try:
        validate_or_raise("schemas/common/envelope.schema.json", req)
        payload = req.get("payload") or {}
        validate_or_raise("schemas/nav/nav_route_request.schema.json", payload)
    except SchemaValidationError as e:
        return {"ok": False, "error": f"bad request: {e}"}

    meta = req["meta"]
    out = envelope("nav.route.result", meta["session_id"], meta.get("trace"), {
        "distance_m": 5200,
        "duration_s": 780,
        "summary": "推荐路线",
        "polyline": "",
        "steps": [{"instruction": "直行 1 公里", "distance_m": 1000}]
    })
    validate_or_raise("schemas/common/envelope.schema.json", out)
    return out

@router.post("/poi")
def poi(req: dict):
    try:
        validate_or_raise("schemas/common/envelope.schema.json", req)
        payload = req.get("payload") or {}
        validate_or_raise("schemas/nav/nav_poi_request.schema.json", payload)
    except SchemaValidationError as e:
        return {"ok": False, "error": f"bad request: {e}"}

    query = str(payload.get("query", "")).strip() or "POI"
    center = payload.get("center", {"lat": 31.23, "lon": 121.47})
    lat = float(center.get("lat", 31.23))
    lon = float(center.get("lon", 121.47))

    meta = req["meta"]
    out = envelope("nav.poi.result", meta["session_id"], meta.get("trace"), {
        "items": [
            {"name": query, "lat": lat, "lon": lon, "address": "Demo Road 1", "distance_m": 850},
            {"name": f"{query} 2", "lat": lat + 0.002, "lon": lon + 0.002, "address": "Demo Road 2", "distance_m": 1350}
        ]
    })
    validate_or_raise("schemas/common/envelope.schema.json", out)
    return out
