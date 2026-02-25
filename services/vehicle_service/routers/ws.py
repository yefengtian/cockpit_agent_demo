from fastapi import APIRouter, WebSocket

router = APIRouter()

@router.websocket("/ws/vehicle")
async def ws_vehicle(ws: WebSocket):
    # Demo: keep connection alive; later push vehicle.event from simulator
    await ws.accept()
    while True:
        await ws.receive_text()