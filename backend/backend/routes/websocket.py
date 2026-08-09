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
from urllib.parse import urlsplit
from fastapi import APIRouter, WebSocket, WebSocketDisconnect, Query
from collections import defaultdict

from auth.security import decode_access_token

router = APIRouter()
logger = logging.getLogger("aic.websocket")

_LOCALHOST_HOSTS = frozenset({"127.0.0.1", "localhost", "::1"})


def _host_is_localhost(host: str) -> bool:
    """Parse a Host header value and compare the host part exactly.

    QA-E2E FIX: startswith(("127.0.0.1", "localhost", "[::1]")) was bypassable
    via a Host header like "127.0.0.1.evil.com", which starts with "127.0.0.1".
    Strip the port (and IPv6 brackets) and compare the exact host.
    """
    if not host:
        return False
    raw = host.strip()
    if raw.startswith("["):  # IPv6 literal, e.g. [::1]:8000
        if "]" in raw:
            raw = raw.split("]", 1)[0]
        else:
            raw = raw[1:]
        raw = raw.lstrip("[")
    else:
        raw = raw.split(":", 1)[0]
    return raw.strip().lower() in _LOCALHOST_HOSTS


def _origin_is_localhost(origin: str) -> bool:
    """Parse an Origin header and check whether its host is localhost.

    QA-E2E FIX: startswith(("http://127.0.0.1", ...)) was bypassable via an
    Origin like "http://127.0.0.1.evil.com". Parse the URL and compare the
    exact hostname.
    """
    if not origin:
        return False
    try:
        hostname = urlsplit(origin).hostname or ""
    except ValueError:
        return False
    return hostname.strip().lower() in _LOCALHOST_HOSTS


def _is_localhost(websocket: WebSocket) -> bool:
    """Check if the WebSocket connection is from localhost (desktop mode)."""
    client = websocket.client
    if client and client.host in ("127.0.0.1", "localhost", "::1"):
        return True
    if _host_is_localhost(websocket.headers.get("host", "")):
        return True
    if _origin_is_localhost(websocket.headers.get("origin", "")):
        return True
    return False


class ConnectionManager:
    """Manages WebSocket connections per channel."""
    def __init__(self):
        self.connections: dict[str, list[WebSocket]] = defaultdict(list)
        self.user_channels: dict[str, set[str]] = defaultdict(set)  # user_id → channels
        self.ws_channels: dict[int, set[str]] = {}  # websocket id → all subscribed channels

    def _get_ws_id(self, ws: WebSocket) -> int:
        """Get a stable identifier for a WebSocket connection object."""
        return id(ws)

    async def connect(self, websocket: WebSocket, channel: str, user_id: str | None = None):
        await websocket.accept()
        self.connections[channel].append(websocket)
        
        # Track this WS's subscriptions to enable proper cleanup (P4 fix)
        ws_id = self._get_ws_id(websocket)
        if ws_id not in self.ws_channels:
            self.ws_channels[ws_id] = set()
        self.ws_channels[ws_id].add(channel)
        
        if user_id:
            self.user_channels[user_id].add(channel)
        logger.info(f"WebSocket connected: channel={channel} user={user_id or 'anonymous'}")

    def disconnect(self, websocket: WebSocket, channel: str, user_id: str | None = None):
        if websocket in self.connections[channel]:
            self.connections[channel].remove(websocket)
        if user_id and user_id in self.user_channels:
            self.user_channels[user_id].discard(channel)

    def disconnect_all(self, websocket: WebSocket, user_id: str | None = None):
        """P4 fix: remove the WebSocket from EVERY channel it subscribed to.

        Multi-channel subscriptions previously leaked — the finally block only
        disconnected the initial channel, leaving dead references in
        self.connections for every extra `subscribe` command.
        """
        ws_id = self._get_ws_id(websocket)
        channels = self.ws_channels.pop(ws_id, set())
        for ch in channels:
            if websocket in self.connections.get(ch, []):
                self.connections[ch].remove(websocket)
            if user_id and user_id in self.user_channels:
                self.user_channels[user_id].discard(ch)
        # Also sweep the initial channel defensively in case connect() tracking missed it
        for ch, conns in list(self.connections.items()):
            if websocket in conns:
                conns.remove(websocket)

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
        logger.info(f"WebSocket disconnected: channel={channel}")
    except Exception as e:
        # M14: json.loads / connect / send can raise non-WebSocketDisconnect
        # errors — the socket must still be removed from the manager.
        logger.warning(f"WebSocket error on channel={channel}: {e}")
    finally:
        # P4 FIX: remove the socket from ALL channels it subscribed to, not just
        # the initial one — multi-channel subscriptions previously leaked dead
        # references into manager.connections for the lifetime of the process.
        manager.disconnect_all(websocket, user_id)
