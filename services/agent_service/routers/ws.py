import json
from fastapi import APIRouter, WebSocket, WebSocketDisconnect
from libs.schema_utils.validate import SchemaValidationError, validate_or_raise
from ..core.runtime import execute_text_plan

router = APIRouter()

@router.websocket("/ws/agent")
async def ws_agent(ws: WebSocket):
    await ws.accept()
    try:
        while True:
            raw = await ws.receive_text()
            msg = json.loads(raw)
            try:
                validate_or_raise("schemas/common/envelope.schema.json", msg)
                utter = msg.get("payload") or {}
                validate_or_raise("schemas/agent/agent_user_utterance.schema.json", utter)
            except SchemaValidationError as e:
                await ws.send_text(json.dumps({"ok": False, "error": f"bad request: {e}"}, ensure_ascii=False))
                continue

            meta = msg["meta"]
            out = execute_text_plan(
                session_id=meta["session_id"],
                trace=meta.get("trace"),
                text=msg["payload"]["text"],
            )
            await ws.send_text(json.dumps(out, ensure_ascii=False))
    except WebSocketDisconnect:
        return
