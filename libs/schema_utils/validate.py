from typing import Any, Dict


class SchemaValidationError(ValueError):
    pass


def _is_number(v: Any) -> bool:
    return isinstance(v, (int, float)) and not isinstance(v, bool)


def _ensure(cond: bool, msg: str) -> None:
    if not cond:
        raise SchemaValidationError(msg)


def _validate_envelope(obj: Dict[str, Any]) -> None:
    _ensure(isinstance(obj, dict), "envelope must be an object")
    _ensure("meta" in obj and "payload" in obj, "envelope requires meta and payload")

    meta = obj["meta"]
    payload = obj["payload"]
    _ensure(isinstance(meta, dict), "meta must be an object")
    _ensure(isinstance(payload, dict), "payload must be an object")

    required_meta = ["message_id", "timestamp_ms", "source", "type", "session_id", "trace"]
    for k in required_meta:
        _ensure(k in meta, f"meta.{k} is required")

    _ensure(isinstance(meta["message_id"], str) and len(meta["message_id"]) >= 8, "invalid meta.message_id")
    _ensure(isinstance(meta["timestamp_ms"], int) and meta["timestamp_ms"] >= 0, "invalid meta.timestamp_ms")
    _ensure(isinstance(meta["type"], str) and len(meta["type"]) > 0, "invalid meta.type")
    _ensure(isinstance(meta["session_id"], str) and len(meta["session_id"]) > 0, "invalid meta.session_id")

    source = meta["source"]
    _ensure(source in {"audio", "agent", "vehicle", "dms", "nav", "ui", "test"}, "invalid meta.source")

    trace = meta["trace"]
    _ensure(isinstance(trace, dict), "meta.trace must be an object")
    _ensure(isinstance(trace.get("trace_id"), str) and len(trace["trace_id"]) >= 8, "invalid trace.trace_id")
    _ensure(isinstance(trace.get("span_id"), str) and len(trace["span_id"]) >= 8, "invalid trace.span_id")


def _validate_agent_utterance(obj: Dict[str, Any]) -> None:
    _ensure(isinstance(obj, dict), "agent utterance must be object")
    _ensure(isinstance(obj.get("text"), str) and len(obj["text"].strip()) > 0, "payload.text is required")
    _ensure(obj.get("input_modality") in {"voice", "touch", "api"}, "invalid payload.input_modality")
    if "language" in obj:
        _ensure(isinstance(obj["language"], str), "payload.language must be string")
    if "speaker_role" in obj:
        _ensure(obj["speaker_role"] in {"driver", "passenger", "unknown"}, "invalid payload.speaker_role")


def _validate_vehicle_command(obj: Dict[str, Any]) -> None:
    _ensure(isinstance(obj, dict), "vehicle command must be object")
    command = obj.get("command")
    args = obj.get("args")
    _ensure(command in {"set_window", "set_ac", "set_fan_speed", "set_ac_mode", "set_recirc", "get_state"}, "invalid command")
    _ensure(isinstance(args, dict), "args must be object")

    if command == "set_window":
        _ensure(args.get("position") in {"FL", "FR", "RL", "RR"}, "invalid set_window.position")
        _ensure(isinstance(args.get("percent"), int) and 0 <= args["percent"] <= 100, "invalid set_window.percent")
    elif command == "set_ac":
        _ensure(_is_number(args.get("temp_c")) and 16 <= float(args["temp_c"]) <= 30, "invalid set_ac.temp_c")
        _ensure(isinstance(args.get("ac_on"), bool), "invalid set_ac.ac_on")
    elif command == "set_fan_speed":
        _ensure(isinstance(args.get("level"), int) and 1 <= args["level"] <= 7, "invalid set_fan_speed.level")
    elif command == "set_ac_mode":
        _ensure(args.get("mode") in {"face", "feet", "defrost", "auto"}, "invalid set_ac_mode.mode")
    elif command == "set_recirc":
        _ensure(isinstance(args.get("recirc_on"), bool), "invalid set_recirc.recirc_on")


def _validate_nav_route_request(obj: Dict[str, Any]) -> None:
    _ensure(isinstance(obj, dict), "nav route request must be object")
    _ensure(isinstance(obj.get("origin"), dict), "origin is required")
    _ensure(isinstance(obj.get("destination"), dict), "destination is required")
    for p in ("origin", "destination"):
        loc = obj[p]
        _ensure(_is_number(loc.get("lat")) and _is_number(loc.get("lon")), f"invalid {p}.lat/lon")
    if "avoid" in obj:
        _ensure(isinstance(obj["avoid"], list), "avoid must be array")
    if "mode" in obj:
        _ensure(obj["mode"] == "driving", "mode must be driving")


def _validate_nav_poi_request(obj: Dict[str, Any]) -> None:
    _ensure(isinstance(obj, dict), "nav poi request must be object")
    _ensure(isinstance(obj.get("center"), dict), "center is required")
    center = obj["center"]
    _ensure(_is_number(center.get("lat")) and _is_number(center.get("lon")), "invalid center.lat/lon")
    _ensure(isinstance(obj.get("query"), str) and len(obj["query"].strip()) > 0, "query is required")
    if "radius_m" in obj:
        _ensure(isinstance(obj["radius_m"], int) and 100 <= obj["radius_m"] <= 50000, "invalid radius_m")
    if "limit" in obj:
        _ensure(isinstance(obj["limit"], int) and 1 <= obj["limit"] <= 20, "invalid limit")


def validate_or_raise(schema_path: str, obj: Dict[str, Any]) -> None:
    if schema_path == "schemas/common/envelope.schema.json":
        _validate_envelope(obj)
    elif schema_path == "schemas/agent/agent_user_utterance.schema.json":
        _validate_agent_utterance(obj)
    elif schema_path == "schemas/vehicle/vehicle_command.schema.json":
        _validate_vehicle_command(obj)
    elif schema_path == "schemas/nav/nav_route_request.schema.json":
        _validate_nav_route_request(obj)
    elif schema_path == "schemas/nav/nav_poi_request.schema.json":
        _validate_nav_poi_request(obj)
    else:
        raise SchemaValidationError(f"unsupported schema validator: {schema_path}")
