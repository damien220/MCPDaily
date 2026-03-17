"""WatchdogTool — monitor directories and auto-organise incoming files.

Payload
-------
{
  "action": "start" | "stop" | "status",
  "path":   "inbox",       # relative to workspace (start only, default ".")
  "dry_run": false         # preview without moving (start only, default false)
}

Result (start)
--------------
{ "watching": "inbox", "pid_key": "inbox", "status": "started" }

Result (status)
---------------
{ "watchers": [{"path": "inbox", "events": 12, "running": true}] }

Result (stop)
-------------
{ "stopped": "inbox" }

Implementation notes
--------------------
- Uses inotify via the ``watchdog`` library (pip install watchdog) when
  available, otherwise falls back to polling every STT_POLL_INTERVAL seconds.
- Each watched directory runs in a background daemon thread; the tool is
  therefore stateful and process-local (not distributed across workers).
- Auto-organise: when a new file appears, waits 2 s for the write to settle
  then calls OrganizeTool on the parent directory.
"""

from __future__ import annotations

import logging
import threading
import time
from pathlib import Path
from typing import TYPE_CHECKING

from core.models import MCPRequest, MCPResponse
from core.tool_base import BaseTool

if TYPE_CHECKING:
    from ..history import OperationLog
    from ..naming import NameFormatter

log = logging.getLogger(__name__)

# Global registry: path-string → _WatchSession
_SESSIONS: dict[str, "_WatchSession"] = {}
_LOCK = threading.Lock()


# ── Watch session ─────────────────────────────────────────────────────────────

class _WatchSession:
    """One background watcher for a single directory."""

    def __init__(
        self,
        watch_path: Path,
        workspace: Path,
        formatter: "NameFormatter",
        operation_log: "OperationLog | None",
        dry_run: bool,
    ) -> None:
        self.watch_path = watch_path
        self.workspace = workspace
        self.formatter = formatter
        self.operation_log = operation_log
        self.dry_run = dry_run
        self.events: int = 0
        self._stop = threading.Event()
        self._thread: threading.Thread | None = None
        self._use_inotify = False

    # ── Public API ────────────────────────────────────────────────────────────

    def start(self) -> None:
        try:
            from watchdog.observers import Observer          # noqa: PLC0415
            from watchdog.events import FileSystemEventHandler  # noqa: PLC0415
            self._use_inotify = True
            self._start_inotify(Observer, FileSystemEventHandler)
        except ImportError:
            log.info("watchdog library not installed; using polling fallback")
            self._start_polling()

    def stop(self) -> None:
        self._stop.set()
        if self._thread:
            self._thread.join(timeout=5)

    @property
    def running(self) -> bool:
        return self._thread is not None and self._thread.is_alive()

    # ── inotify backend ───────────────────────────────────────────────────────

    def _start_inotify(self, Observer, FileSystemEventHandler) -> None:
        session = self

        class _Handler(FileSystemEventHandler):
            def on_created(self, event):
                if not event.is_directory:
                    session._on_new_file(Path(event.src_path))

        handler = _Handler()
        observer = Observer()
        observer.schedule(handler, str(self.watch_path), recursive=False)
        observer.start()

        def _run():
            while not session._stop.wait(timeout=1):
                pass
            observer.stop()
            observer.join()

        self._thread = threading.Thread(target=_run, daemon=True, name=f"watchdog-{self.watch_path.name}")
        self._thread.start()
        log.info("inotify watcher started: %s", self.watch_path)

    # ── Polling backend ───────────────────────────────────────────────────────

    def _start_polling(self, interval: float = 3.0) -> None:
        watch_path = self.watch_path

        def _run():
            known: set[Path] = set(watch_path.iterdir()) if watch_path.exists() else set()
            while not self._stop.wait(timeout=interval):
                if not watch_path.exists():
                    continue
                current = set(watch_path.iterdir())
                new_files = {p for p in (current - known) if p.is_file()}
                known = current
                for f in new_files:
                    self._on_new_file(f)

        self._thread = threading.Thread(target=_run, daemon=True, name=f"watchdog-poll-{self.watch_path.name}")
        self._thread.start()
        log.info("polling watcher started: %s (interval=%.1fs)", self.watch_path, interval)

    # ── File handler ──────────────────────────────────────────────────────────

    def _on_new_file(self, file_path: Path) -> None:
        self.events += 1
        log.info("watchdog: new file detected: %s", file_path)
        # Wait 2 s for write to settle (avoid partial reads)
        time.sleep(2)
        if not file_path.exists():
            return
        try:
            self._organise(file_path)
        except Exception as exc:
            log.error("watchdog: auto-organise failed for %s: %s", file_path, exc)

    def _organise(self, file_path: Path) -> None:
        """Apply naming rules to a single newly-arrived file."""
        try:
            new_path = self.formatter.format_path(file_path)
        except Exception as exc:
            log.warning("watchdog: formatter error for %s: %s", file_path, exc)
            return

        if new_path == file_path:
            return  # already compliant

        if self.dry_run:
            log.info("watchdog [dry-run]: would rename %s → %s", file_path.name, new_path.name)
            return

        new_path.parent.mkdir(parents=True, exist_ok=True)
        file_path.rename(new_path)
        log.info("watchdog: organised %s → %s", file_path, new_path)

        if self.operation_log:
            from ..history import Operation  # noqa: PLC0415
            self.operation_log.record(Operation(
                tool="watchdog",
                action="move",
                source=str(file_path.relative_to(self.workspace)),
                destination=str(new_path.relative_to(self.workspace)),
            ))


# ── WatchdogTool ─────────────────────────────────────────────────────────────

class WatchdogTool(BaseTool):
    """Monitor directories and automatically organise new files on arrival."""

    name = "watchdogtool"
    description = (
        "Start/stop a background directory watcher. "
        "New files are automatically renamed and categorised by the naming rules engine."
    )

    def __init__(
        self,
        workspace: Path,
        formatter: "NameFormatter",
        operation_log: "OperationLog | None" = None,
    ) -> None:
        self._workspace = workspace
        self._formatter = formatter
        self._operation_log = operation_log

    def handle(self, request: MCPRequest) -> MCPResponse:
        payload = request.payload or {}
        action = payload.get("action", "status").lower()

        if action == "status":
            return self._status(request)
        if action == "start":
            return self._start(request, payload)
        if action == "stop":
            return self._stop(request, payload)

        return MCPResponse.failure(request, f"Unknown action '{action}'. Use start | stop | status.")

    # ── Actions ───────────────────────────────────────────────────────────────

    def _status(self, request: MCPRequest) -> MCPResponse:
        with _LOCK:
            watchers = [
                {
                    "path": str(Path(k).relative_to(self._workspace)),
                    "events": s.events,
                    "running": s.running,
                    "dry_run": s.dry_run,
                }
                for k, s in _SESSIONS.items()
            ]
        return MCPResponse.success(request, {"watchers": watchers, "count": len(watchers)})

    def _start(self, request: MCPRequest, payload: dict) -> MCPResponse:
        rel = payload.get("path", ".")
        dry_run: bool = bool(payload.get("dry_run", False))

        watch_path = (self._workspace / rel).resolve()
        if not watch_path.is_relative_to(self._workspace):
            return MCPResponse.failure(request, "Path escapes workspace.")

        watch_path.mkdir(parents=True, exist_ok=True)
        key = str(watch_path)

        with _LOCK:
            if key in _SESSIONS and _SESSIONS[key].running:
                return MCPResponse.success(request, {
                    "status": "already_running",
                    "path": rel,
                    "events": _SESSIONS[key].events,
                })
            session = _WatchSession(
                watch_path=watch_path,
                workspace=self._workspace,
                formatter=self._formatter,
                operation_log=self._operation_log,
                dry_run=dry_run,
            )
            session.start()
            _SESSIONS[key] = session

        return MCPResponse.success(request, {
            "status": "started",
            "path": rel,
            "dry_run": dry_run,
            "backend": "inotify" if session._use_inotify else "polling",
        })

    def _stop(self, request: MCPRequest, payload: dict) -> MCPResponse:
        rel = payload.get("path", ".")
        watch_path = (self._workspace / rel).resolve()
        key = str(watch_path)

        with _LOCK:
            session = _SESSIONS.pop(key, None)

        if session is None:
            return MCPResponse.failure(request, f"No active watcher for '{rel}'.")

        session.stop()
        return MCPResponse.success(request, {"status": "stopped", "path": rel, "events": session.events})
