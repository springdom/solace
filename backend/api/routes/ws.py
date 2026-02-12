"""WebSocket endpoint for real-time alert/incident updates."""

import json
import logging
import secrets

from fastapi import APIRouter, WebSocket, WebSocketDisconnect

from backend.config import get_settings

logger = logging.getLogger(__name__)

router = APIRouter(tags=["websocket"])

settings = get_settings()


class ConnectionManager:
    """Manages active WebSocket connections and broadcasts events."""

    def __init__(self) -> None:
        self._connections: set[WebSocket] = set()

    async def connect(self, ws: WebSocket) -> None:
        await ws.accept()
        self._connections.add(ws)
        logger.info(f"WebSocket connected ({len(self._connections)} active)")

    def disconnect(self, ws: WebSocket) -> None:
        self._connections.discard(ws)
        logger.info(f"WebSocket disconnected ({len(self._connections)} active)")

    async def broadcast(self, event: dict) -> None:
        """Send an event to all connected clients."""
        if not self._connections:
            return
        payload = json.dumps(event)
        dead: list[WebSocket] = []
        for ws in self._connections:
            try:
                await ws.send_text(payload)
            except Exception:
                dead.append(ws)
        for ws in dead:
            self._connections.discard(ws)


manager = ConnectionManager()


def _check_ws_auth(api_key: str | None) -> bool:
    """Validate API key for WebSocket connections."""
    if settings.is_dev and settings.api_key == "":
        return True
    if not api_key:
        return False
    return secrets.compare_digest(api_key, settings.api_key)


@router.websocket("/ws")
async def websocket_endpoint(ws: WebSocket) -> None:
    """Real-time event stream.

    Clients connect and receive JSON events when alerts or incidents
    are created, updated, or resolved.

    Auth: pass API key as ?token= query param.

    Event format:
        {"type": "alert.created", "data": {...}}
        {"type": "incident.updated", "data": {...}}
    """
    token = ws.query_params.get("token")
    if not _check_ws_auth(token):
        await ws.close(code=4003, reason="Invalid or missing API key")
        return

    await manager.connect(ws)
    try:
        while True:
            # Keep connection alive; clients can send pings
            data = await ws.receive_text()
            if data == "ping":
                await ws.send_text(json.dumps({"type": "pong"}))
    except WebSocketDisconnect:
        pass
    finally:
        manager.disconnect(ws)


async def emit_event(event_type: str, data: dict) -> None:
    """Broadcast an event to all connected WebSocket clients.

    Call this from services when state changes occur.
    """
    await manager.broadcast({"type": event_type, "data": data})
