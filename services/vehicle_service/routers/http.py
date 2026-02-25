from typing import Optional
from fastapi import APIRouter
from libs.log.tracing import now_ms, mk_trace, new_id
from ..simulator.state import STATE

router = APIRouter()

def envelope(source: str, typ: str, session_id: str, trace: Optional[dict], payload: dict):
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

@router.get("/state")
def get_state():
    return envelope("vehicle", "vehicle.state", "demo", None, {
        "speed_kph": STATE.speed_kph,
        "gear": STATE.gear,
        "windows": STATE.windows,
        "ac": STATE.ac
    })

@router.post("/command")
def command(req: dict):
    meta = req.get("meta", {})
    session_id = meta.get("session_id", "demo")
    trace = meta.get("trace")
    cmd = (req.get("payload") or {})
    c = cmd.get("command")
    args = cmd.get("args") or {}

    err = None
    if c == "set_window":
        pos, pct = args.get("position"), args.get("percent")
        if pos in STATE.windows and isinstance(pct, int) and 0 <= pct <= 100:
            STATE.windows[pos] = pct
        else:
            err = {"code": "bad_args", "message": "invalid window args", "detail": {"args": args}, "retryable": False}
    elif c == "set_ac":
        temp, on = args.get("temp_c"), args.get("ac_on")
        if isinstance(temp, (int, float)) and 16 <= temp <= 30 and isinstance(on, bool):
            STATE.ac["temp_c"] = float(temp)
            STATE.ac["ac_on"] = on
        else:
            err = {"code": "bad_args", "message": "invalid ac args", "detail": {"args": args}, "retryable": False}
    elif c == "set_fan_speed":
        lvl = args.get("level")
        if isinstance(lvl, int) and 1 <= lvl <= 7:
            STATE.ac["fan_level"] = lvl
        else:
            err = {"code": "bad_args", "message": "invalid fan args", "detail": {"args": args}, "retryable": False}
    elif c == "set_ac_mode":
        mode = args.get("mode")
        if mode in ["face", "feet", "defrost", "auto"]:
            STATE.ac["mode"] = mode
        else:
            err = {"code": "bad_args", "message": "invalid mode", "detail": {"args": args}, "retryable": False}
    elif c == "set_recirc":
        ro = args.get("recirc_on")
        if isinstance(ro, bool):
            STATE.ac["recirc_on"] = ro
        else:
            err = {"code": "bad_args", "message": "invalid recirc arg", "detail": {"args": args}, "retryable": False}
    elif c == "get_state":
        pass
    else:
        err = {"code": "unknown_command", "message": f"unknown command: {c}", "detail": {"command": c}, "retryable": False}

    event_payload = {
        "event": "command_rejected" if err else "state_changed",
        "state": {
            "speed_kph": STATE.speed_kph,
            "gear": STATE.gear,
            "windows": STATE.windows,
            "ac": STATE.ac
        }
    }
    if err:
        event_payload["error"] = err

    return envelope("vehicle", "vehicle.event", session_id, trace, event_payload)