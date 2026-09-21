import json
import logging
from typing import Dict, List, Set
from fastapi import APIRouter, WebSocket, WebSocketDisconnect

logger = logging.getLogger(__name__)

router = APIRouter()


class ConnectionManager:
    """
    Manages real-time WebSocket subscriber connections keyed by run_id,
    with broadcast capability for agent state transitions.
    """
    def __init__(self):
        # run_id -> set of WebSockets
        self.active_connections: Dict[str, Set[WebSocket]] = {}
        # Global broadcast listeners (e.g. dashboard monitoring all runs)
        self.global_connections: Set[WebSocket] = set()

    async def connect(self, websocket: WebSocket, run_id: str):
        await websocket.accept()
        if run_id not in self.active_connections:
            self.active_connections[run_id] = set()
        self.active_connections[run_id].add(websocket)
        logger.info(f"WebSocket connected for run_id: {run_id}")

    def disconnect(self, websocket: WebSocket, run_id: str):
        if run_id in self.active_connections:
            self.active_connections[run_id].discard(websocket)
            if not self.active_connections[run_id]:
                del self.active_connections[run_id]
        self.global_connections.discard(websocket)
        logger.info(f"WebSocket disconnected for run_id: {run_id}")

    async def broadcast_to_run(self, run_id: str, message: dict):
        payload = json.dumps(message, default=str)
        # Send to specific run subscribers
        if run_id in self.active_connections:
            dead_sockets = set()
            for ws in self.active_connections[run_id]:
                try:
                    await ws.send_text(payload)
                except Exception:
                    dead_sockets.add(ws)
            for ws in dead_sockets:
                self.active_connections[run_id].discard(ws)

        # Also send to global listeners
        if self.global_connections:
            dead_globals = set()
            for ws in self.global_connections:
                try:
                    await ws.send_text(payload)
                except Exception:
                    dead_globals.add(ws)
            for ws in dead_globals:
                self.global_connections.discard(ws)


manager = ConnectionManager()


@router.websocket("/ws/agent-stream/{run_id}")
async def agent_stream_websocket(websocket: WebSocket, run_id: str):
    """
    Duplex WebSocket connection endpoint for real-time node transitions,
    state updates, and agent thoughts.
    """
    await manager.connect(websocket, run_id)
    try:
        # Send initial confirmation message
        await websocket.send_json({
            "event": "ws_connected",
            "run_id": run_id,
            "message": f"Connected to agent stream channel for {run_id}"
        })

        while True:
            # Maintain connection and listen for client messages (e.g. heartbeat or interrupt)
            data = await websocket.receive_text()
            try:
                msg = json.loads(data)
                if msg.get("type") == "ping":
                    await websocket.send_json({"type": "pong", "run_id": run_id})
            except Exception:
                pass
    except WebSocketDisconnect:
        manager.disconnect(websocket, run_id)
    except Exception as e:
        logger.warning(f"WebSocket exception: {e}")
        manager.disconnect(websocket, run_id)
