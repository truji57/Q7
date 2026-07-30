"""
Q7 Backend - Main Application
"""
import asyncio
import logging
import threading
from contextlib import asynccontextmanager

from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse

from app.config import settings
from app.database import init_db
from app.engine.orchestrator import OrchestratorEngine
from app.ws.manager import manager
from app.api.routes import router

logging.basicConfig(level=logging.INFO)
log = logging.getLogger("Q7Backend")

orchestrator: OrchestratorEngine | None = None


async def broadcast_loop():
    while True:
        try:
            if orchestrator:
                orchestrator.poll_signals()
                state = orchestrator.get_dashboard_state()
                await manager.broadcast(state)
        except Exception as e:
            log.error(f"Broadcast error: {e}")
        await asyncio.sleep(0.2)


@asynccontextmanager
async def lifespan(app: FastAPI):
    global orchestrator

    init_db()
    log.info("Database initialized")

    orchestrator = OrchestratorEngine()
    loop = asyncio.get_running_loop()
    orchestrator.set_ws_broadcast(lambda data: asyncio.run_coroutine_threadsafe(
        manager.broadcast(data),
        loop
    ))

    broadcast_task = asyncio.create_task(broadcast_loop())

    log.info(f"Q7 Backend ready on port 8005")

    yield

    broadcast_task.cancel()
    log.info("Q7 Backend shutting down")


app = FastAPI(
    title="Q7 API",
    version="1.0.0",
    lifespan=lifespan,
    docs_url=None,
    redoc_url=None
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(router)


@app.websocket("/ws")
async def websocket_endpoint(ws: WebSocket):
    await ws.accept()
    await manager.connect(ws)
    try:
        if orchestrator:
            await ws.send_json(orchestrator.get_dashboard_state())
        while True:
            try:
                data = await asyncio.wait_for(ws.receive_text(), timeout=30)
                if data == "ping":
                    await ws.send_text("pong")
            except asyncio.TimeoutError:
                if orchestrator:
                    await ws.send_json(orchestrator.get_dashboard_state())
    except WebSocketDisconnect:
        pass
    except Exception:
        pass
    finally:
        manager.disconnect(ws)


import os
frontend_path = os.path.join(os.path.dirname(__file__), "..", "..", "frontend", "dist")
if os.path.exists(frontend_path):
    app.mount("/assets", StaticFiles(directory=os.path.join(frontend_path, "assets")), name="assets")

    @app.get("/{full_path:path}")
    async def serve_frontend(full_path: str):
        file_path = os.path.join(frontend_path, full_path)
        if os.path.exists(file_path) and os.path.isfile(file_path):
            return FileResponse(file_path)
        return FileResponse(os.path.join(frontend_path, "index.html"))
