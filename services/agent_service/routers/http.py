from fastapi import APIRouter
from libs.schema_utils.validate import SchemaValidationError, validate_or_raise
from ..core.runtime import execute_text_plan

router = APIRouter()

@router.get("/health")
def health():
    return {"ok": True}

@router.post("/chat")
def chat(req: dict):
    try:
        validate_or_raise("schemas/common/envelope.schema.json", req)
        utter = req.get("payload") or {}
        validate_or_raise("schemas/agent/agent_user_utterance.schema.json", utter)
    except SchemaValidationError as e:
        return {"ok": False, "error": f"bad request: {e}"}

    meta = req["meta"]
    return execute_text_plan(
        session_id=meta["session_id"],
        trace=meta.get("trace"),
        text=req["payload"]["text"],
    )
