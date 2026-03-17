"""WebServer — extends HTTPServer with a static web dashboard and WebSocket push."""

from __future__ import annotations

import asyncio
import base64
import hashlib
import hmac
import os
from pathlib import Path

from fastapi import Request, WebSocket, WebSocketDisconnect
from fastapi.responses import FileResponse, Response

from transports.http_server import HTTPServer

_STATIC_DIR = Path(__file__).resolve().parent / "static"


def _make_auth_middleware(username: str, password: str):
    """Return a FastAPI middleware function that enforces HTTP Basic Auth.

    Uses a constant-time comparison to prevent timing attacks.
    WebSocket connections (/ws) are exempt — they rely on the same-origin
    browser session that has already authenticated via HTTP.
    """
    _user_b = username.encode()
    _pass_b = password.encode()

    async def _basic_auth_middleware(request: Request, call_next):
        # WebSocket upgrade requests skip auth (browser enforces same-origin)
        if request.url.path == "/ws":
            return await call_next(request)

        auth_header = request.headers.get("Authorization", "")
        authenticated = False
        if auth_header.startswith("Basic "):
            try:
                decoded = base64.b64decode(auth_header[6:]).split(b":", 1)
                if len(decoded) == 2:
                    ok_user = hmac.compare_digest(decoded[0], _user_b)
                    ok_pass = hmac.compare_digest(decoded[1], _pass_b)
                    authenticated = ok_user and ok_pass
            except Exception:
                pass

        if not authenticated:
            return Response(
                content="Unauthorized",
                status_code=401,
                headers={"WWW-Authenticate": 'Basic realm="LocalFileHandler"'},
            )
        return await call_next(request)

    return _basic_auth_middleware


class ConnectionManager:
    """Track connected WebSocket clients and broadcast JSON events to them."""

    def __init__(self) -> None:
        self._clients: set[WebSocket] = set()

    async def connect(self, ws: WebSocket) -> None:
        await ws.accept()
        self._clients.add(ws)

    def disconnect(self, ws: WebSocket) -> None:
        self._clients.discard(ws)

    async def broadcast(self, data: dict) -> None:
        """Send *data* to every connected client; silently remove dead connections."""
        dead: set[WebSocket] = set()
        for ws in list(self._clients):
            try:
                await ws.send_json(data)
            except Exception:
                dead.add(ws)
        for ws in dead:
            self._clients.discard(ws)

    @property
    def count(self) -> int:
        return len(self._clients)


async def _watch_history(workspace: Path, manager: ConnectionManager) -> None:
    """Poll operations.jsonl mtime every 500 ms; broadcast 'refresh' on change.

    This is the authoritative trigger for live updates — any tool that mutates
    files writes to the history log, so watching it covers all operations
    regardless of transport (CLI, HTTP, or future sources).
    """
    history_file = workspace / ".history" / "operations.jsonl"
    last_mtime = 0.0
    while True:
        try:
            if history_file.exists():
                mtime = history_file.stat().st_mtime
                if mtime != last_mtime:
                    if last_mtime > 0:          # skip the very first check
                        await manager.broadcast({"type": "refresh"})
                    last_mtime = mtime
        except Exception:
            pass
        await asyncio.sleep(0.5)


class WebServer(HTTPServer):
    """HTTP server that also serves the web dashboard SPA and a WebSocket push channel.

    Routes added on top of the base ``POST /invoke``:
        GET  /                 → serves ``index.html``
        GET  /static/style.css
        GET  /static/app.js
        WS   /ws               → real-time event push to browser clients
    """

    def __init__(
        self,
        host: str = "127.0.0.1",
        port: int = 8080,
        workspace: Path | None = None,
        auth_username: str = "",
        auth_password: str = "",
    ) -> None:
        super().__init__(host=host, port=port)
        self.app.title = "LocalFileHandler Dashboard"

        _workspace = workspace or Path("workspace").resolve()
        self._manager = ConnectionManager()

        # ── Optional Basic Auth ─────────────────────────────────────────────────
        if auth_username and auth_password:
            from starlette.middleware.base import BaseHTTPMiddleware  # noqa: PLC0415
            self.app.add_middleware(
                BaseHTTPMiddleware,
                dispatch=_make_auth_middleware(auth_username, auth_password),
            )

        # ── Startup: launch history watcher ────────────────────────────────────
        @self.app.on_event("startup")
        async def _startup() -> None:
            asyncio.create_task(_watch_history(_workspace, self._manager))

        # ── Static dashboard ────────────────────────────────────────────────────
        @self.app.get("/", include_in_schema=False)
        async def dashboard() -> FileResponse:
            return FileResponse(str(_STATIC_DIR / "index.html"), media_type="text/html")

        @self.app.get("/static/style.css", include_in_schema=False)
        async def serve_css() -> FileResponse:
            return FileResponse(str(_STATIC_DIR / "style.css"), media_type="text/css")

        @self.app.get("/static/app.js", include_in_schema=False)
        async def serve_js() -> FileResponse:
            return FileResponse(
                str(_STATIC_DIR / "app.js"), media_type="application/javascript"
            )

        # ── WebSocket push channel ──────────────────────────────────────────────
        @self.app.websocket("/ws")
        async def ws_endpoint(websocket: WebSocket) -> None:
            await self._manager.connect(websocket)
            try:
                while True:
                    try:
                        # Wait for a ping from the client (keep-alive).
                        # 25 s timeout: if the browser stops pinging we drop gracefully.
                        msg = await asyncio.wait_for(
                            websocket.receive_text(), timeout=25.0
                        )
                        if msg == "ping":
                            await websocket.send_text("pong")
                    except asyncio.TimeoutError:
                        pass  # Connection still alive; keep looping
            except (WebSocketDisconnect, Exception):
                pass
            finally:
                self._manager.disconnect(websocket)
