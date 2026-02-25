from fastapi import FastAPI
from .routers.http import router as http_router

app = FastAPI(title="nav_service")
app.include_router(http_router)