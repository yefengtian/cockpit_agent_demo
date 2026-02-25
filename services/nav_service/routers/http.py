import os
from typing import Optional
from fastapi import APIRouter
from libs.log.tracing import now_ms, mk_trace, new_id
from libs.config import get_setting
from libs.schema_utils.validate import SchemaValidationError, validate_or_raise
from ..providers import AmapMCPProvider, MCPError

router = APIRouter()
AMAP = AmapMCPProvider()
LAST_PROVIDER_USED = "unknown"
LAST_MCP_ERROR = ""


def _provider_mode() -> str:
    return str(get_setting("nav.provider", os.getenv("NAV_PROVIDER", "stub"))).strip().lower()

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


@router.get("/debug/provider")
def debug_provider():
    amap_key = ""
    if isinstance(AMAP.extra_env, dict):
        amap_key = str(AMAP.extra_env.get("AMAP_MAPS_API_KEY", ""))
    return {
        "provider_mode": _provider_mode(),
        "amap_mcp_command_configured": bool(AMAP.command),
        "amap_maps_api_key_configured": bool(amap_key.strip()),
        "last_provider_used": LAST_PROVIDER_USED,
        "last_mcp_error": LAST_MCP_ERROR,
    }

@router.post("/route")
def route(req: dict):
    global LAST_PROVIDER_USED, LAST_MCP_ERROR
    try:
        validate_or_raise("schemas/common/envelope.schema.json", req)
        payload = req.get("payload") or {}
        validate_or_raise("schemas/nav/nav_route_request.schema.json", payload)
    except SchemaValidationError as e:
        return {"ok": False, "error": f"bad request: {e}"}

    meta = req["meta"]
    summary = "推荐路线"
    distance_m = 5200
    duration_s = 780
    polyline = ""
    steps = [{"instruction": "直行 1 公里", "distance_m": 1000}]

    if _provider_mode() == "amap_mcp":
        try:
            data = AMAP.plan_route(
                origin=payload["origin"],
                destination=payload["destination"],
                mode=payload.get("mode", "driving"),
                avoid=payload.get("avoid", []),
            )
            LAST_PROVIDER_USED = "amap_mcp"
            LAST_MCP_ERROR = ""
            distance_m = float(data.get("distance_m", distance_m))
            duration_s = float(data.get("duration_s", duration_s))
            summary = str(data.get("summary", summary))
            polyline = str(data.get("polyline", polyline))
            raw_steps = data.get("steps")
            if isinstance(raw_steps, list) and raw_steps:
                steps = raw_steps
        except MCPError as e:
            LAST_PROVIDER_USED = "stub_fallback"
            LAST_MCP_ERROR = str(e)
            summary = f"高德MCP不可用，已回退内置导航: {e}"
    else:
        LAST_PROVIDER_USED = "stub"
        LAST_MCP_ERROR = ""

    out = envelope("nav.route.result", meta["session_id"], meta.get("trace"), {
        "distance_m": distance_m,
        "duration_s": duration_s,
        "summary": summary,
        "polyline": polyline,
        "steps": steps,
    })
    validate_or_raise("schemas/common/envelope.schema.json", out)
    return out

@router.post("/poi")
def poi(req: dict):
    global LAST_PROVIDER_USED, LAST_MCP_ERROR
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
    items = [
        {"name": query, "lat": lat, "lon": lon, "address": "Demo Road 1", "distance_m": 850},
        {"name": f"{query} 2", "lat": lat + 0.002, "lon": lon + 0.002, "address": "Demo Road 2", "distance_m": 1350}
    ]

    if _provider_mode() == "amap_mcp":
        try:
            data = AMAP.search_poi(
                center=center,
                query=query,
                radius_m=int(payload.get("radius_m", 5000)),
                limit=int(payload.get("limit", 5)),
            )
            raw_items = data.get("items")
            if isinstance(raw_items, list) and raw_items:
                items = raw_items
                LAST_PROVIDER_USED = "amap_mcp"
                LAST_MCP_ERROR = ""
            else:
                LAST_PROVIDER_USED = "stub_fallback"
                LAST_MCP_ERROR = "mcp returned no usable poi items"
        except MCPError as e:
            LAST_PROVIDER_USED = "stub_fallback"
            LAST_MCP_ERROR = str(e)
    else:
        LAST_PROVIDER_USED = "stub"
        LAST_MCP_ERROR = ""

    meta = req["meta"]
    out = envelope("nav.poi.result", meta["session_id"], meta.get("trace"), {
        "items": items
    })
    validate_or_raise("schemas/common/envelope.schema.json", out)
    return out
