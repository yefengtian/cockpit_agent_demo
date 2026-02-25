import asyncio
import json
from typing import Dict, Set
from fastapi import WebSocket

class TopicBus:
    def __init__(self) -> None:
        self._topics: Dict[str, Set[WebSocket]] = {}
        self._lock = asyncio.Lock()

    async def subscribe(self, topic: str, ws: WebSocket) -> None:
        async with self._lock:
            self._topics.setdefault(topic, set()).add(ws)

    async def unsubscribe(self, topic: str, ws: WebSocket) -> None:
        async with self._lock:
            if topic in self._topics:
                self._topics[topic].discard(ws)
                if not self._topics[topic]:
                    del self._topics[topic]

    async def publish(self, topic: str, message: dict) -> None:
        # Broadcast best-effort
        async with self._lock:
            conns = list(self._topics.get(topic, set()))
        if not conns:
            return
        data = json.dumps(message, ensure_ascii=False)
        dead = []
        for ws in conns:
            try:
                await ws.send_text(data)
            except Exception:
                dead.append(ws)
        if dead:
            async with self._lock:
                for ws in dead:
                    self._topics.get(topic, set()).discard(ws)