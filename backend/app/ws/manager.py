"""
Q7 Backend - WebSocket Manager
"""
import json
import logging
from fastapi import WebSocket

log = logging.getLogger("Q7Backend.WS")


class ConnectionManager:
    def __init__(self):
        self.active_connections: list[WebSocket] = []

    async def connect(self, ws: WebSocket):
        self.active_connections.append(ws)
        log.info(f"WS client connected ({len(self.active_connections)} total)")

    def disconnect(self, ws: WebSocket):
        if ws in self.active_connections:
            self.active_connections.remove(ws)
        log.info(f"WS client disconnected ({len(self.active_connections)} remaining)")

    async def broadcast(self, data: dict):
        disconnected = []
        payload = json.dumps(data)
        for ws in self.active_connections:
            try:
                await ws.send_text(payload)
            except:
                disconnected.append(ws)
        for ws in disconnected:
            self.disconnect(ws)


manager = ConnectionManager()
