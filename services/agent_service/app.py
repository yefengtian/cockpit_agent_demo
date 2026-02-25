from fastapi import FastAPI
from .routers.http import router as http_router
from .routers.ws import router as ws_router

app = FastAPI(title="agent_service")
app.include_router(http_router)
app.include_router(ws_router)