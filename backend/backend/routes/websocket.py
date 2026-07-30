"""AIC Platform — WebSocket Routes for realtime updates.

Features:
- JWT auth on connection (token as query param)
- Unauthenticated access allowed from localhost (desktop mode)
- Channel-based pub/sub
- Event broadcast from dispatcher/workers
- Auto-cleanup of dead connections
"""
import json
import logging
from datetime import datetime, timezone
from fastapi import APIRouter, WebSocket, WebSocketDisconnect, Query
from collections import defaultdict

from auth.security import decode_access_token

router = APIRouter()
logger = logging.getLogger("aic.websocket")


def _is_localhost(websocket: WebSocket) -> bool:
    """Check if the WebSocket connection is from localhost (desktop mode)."""
    host = websocket.headers.get("host", "")
    origin = websocket.headers.get("origin", "")
    client = websocket.client
    if client and client.host in ("127.0.0.1", "localhost", "::1"):
        return True
    if host.startswith(("127.0.0.1", "localhost", "[::1]")):
        return True
    if origin.startswith(("http://127.0.0.1", "http://localhost", "http://[::1]")):
        return True
    return False


class ConnectionManager:
    """Manages WebSocket connections per channel."""
    def __init__(self):
        self.connections: dict[str, list[WebSocket]] = defaultdict(list)
        self.user_channels: dict[str, set[str]] = defaultdict(set)  # user_id → channels

    async def connect(self, websocket: WebSocket, channel: str, user_id: str | None = None):
        await websocket.accept()
        self.connections[channel].append(websocket)
        if user_id:
            self.user_channels[user_id].add(channel)
        logger.info(f"WebSocket connected: channel={channel} user={user_id or 'anonymous'}")

    def disconnect(self, websocket: WebSocket, channel: str, user_id: str | None = None):
        if websocket in self.connections[channel]:
            self.connections[channel].remove(websocket)
        if user_id and user_id in self.user_channels:
            self.user_channels[user_id].discard(channel)

    async def broadcast(self, channel: str, message: dict):
        dead = []
        for ws in self.connections.get(channel, []):
            try:
                await ws.send_json(message)
            except Exception:
                dead.append(ws)
        for ws in dead:
            self.disconnect(ws, channel)

    async def broadcast_all(self, message: dict):
        """Broadcast to all channels."""
        for channel in list(self.connections.keys()):
            await self.broadcast(channel, message)

    def connection_count(self) -> dict:
        return {ch: len(conns) for ch, conns in self.connections.items()}


manager = ConnectionManager()


async def broadcast_event(event_type: str, data: dict, channel: str = "general"):
    """Broadcast an event to all connected clients on a channel."""
    await manager.broadcast(channel, {
        "type": event_type,
        "data": data,
        "timestamp": datetime.now(timezone.utc).isoformat(),
    })


async def broadcast_task_event(event_type: str, task_id: str, data: dict, channel: str = "general"):
    """Broadcast a task-related event."""
    await manager.broadcast(channel, {
        "type": event_type,
        "data": {**data, "task_id": task_id},
        "timestamp": datetime.now(timezone.utc).isoformat(),
    })


async def broadcast_worker_event(event_type: str, worker_id: str, data: dict, channel: str = "general"):
    """Broadcast a worker-related event."""
    await manager.broadcast(channel, {
        "type": event_type,
        "data": {**data, "worker_id": worker_id},
        "timestamp": datetime.now(timezone.utc).isoformat(),
    })


@router.websocket("/{channel}")
async def websocket_endpoint(
    websocket: WebSocket,
    channel: str,
    token: str | None = Query(default=None),
):
    """WebSocket endpoint with optional JWT auth for localhost.

    Connect with: ws://host/ws/general?token=<jwt>
    Desktop mode: token optional for localhost connections.
    """
    # Auth check — allow unauthenticated access from localhost (desktop mode)
    user_id = None
    if token:
        claims = decode_access_token(token)
        if claims:
            user_id = claims.get("sub")
        else:
            await websocket.close(code=4001, reason="Invalid token")
            return
    elif not _is_localhost(websocket):
        # Require auth for non-localhost connections
        await websocket.close(code=4001, reason="Token required")
        return
    else:
        logger.info("WebSocket connected without auth (localhost/desktop mode)")

    await manager.connect(websocket, channel, user_id)

    try:
        while True:
            data = await websocket.receive_text()
            msg = json.loads(data) if data.startswith("{") else {"text": data}

            # Handle subscription commands
            if msg.get("type") == "subscribe":
                sub_channel = msg.get("channel", "general")
                await manager.connect(websocket, sub_channel, user_id)
                await websocket.send_json({
                    "type": "subscribed",
                    "data": {"channel": sub_channel},
                    "timestamp": datetime.now(timezone.utc).isoformat(),
                })
            elif msg.get("type") == "ping":
                await websocket.send_json({
                    "type": "pong",
                    "timestamp": datetime.now(timezone.utc).isoformat(),
                })
            else:
                await websocket.send_json({
                    "type": "ack",
                    "data": msg,
                    "timestamp": datetime.now(timezone.utc).isoformat(),
                })
    except WebSocketDisconnect:
        manager.disconnect(websocket, channel, user_id)
        logger.info(f"WebSocket disconnected: channel={channel}")
