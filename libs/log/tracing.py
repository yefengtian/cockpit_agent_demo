import time
import uuid
from typing import Dict, Optional, Any

def now_ms() -> int:
    return int(time.time() * 1000)

def new_id(prefix: str = "") -> str:
    return (prefix + uuid.uuid4().hex)[:24]

def mk_trace(parent_trace: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    parent_trace = parent_trace or {}
    trace_id = parent_trace.get("trace_id") or uuid.uuid4().hex
    parent_span = parent_trace.get("span_id")
    span_id = uuid.uuid4().hex[:16]
    trace: Dict[str, Any] = {"trace_id": trace_id, "span_id": span_id, "tags": {}}
    if parent_span:
        trace["parent_span_id"] = parent_span
    # merge tags (best-effort)
    tags = parent_trace.get("tags")
    if isinstance(tags, dict):
        trace["tags"].update({str(k): str(v) for k, v in tags.items()})
    return trace
