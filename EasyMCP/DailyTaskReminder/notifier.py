"""Notification delivery for DailyTaskReminder."""

from __future__ import annotations

import shutil
import subprocess
import sys
from typing import Any, Dict

from . import config

# ANSI escape codes
_BOLD = "\033[1m"
_YELLOW = "\033[33m"
_RESET = "\033[0m"


class Notifier:
    """Delivers reminder notifications via terminal and desktop."""

    def __init__(self, app_name: str | None = None) -> None:
        self.app_name = app_name or config.APP_NAME
        self._has_notify_send: bool | None = None

    def notify(self, task: Dict[str, Any]) -> None:
        """Send both terminal and desktop notifications for a task."""
        self.terminal_notify(task)
        self.desktop_notify(task)

    def terminal_notify(self, task: Dict[str, Any]) -> None:
        """Print a colored reminder to stdout."""
        title = task.get("title", "Untitled")
        due_part = ""
        if task.get("due_at"):
            due_part = f" (due: {task['due_at']})"

        msg = f"\n{_BOLD}{_YELLOW}[REMINDER]{_RESET} {_BOLD}{title}{_RESET}{due_part}\n"
        sys.stdout.write(msg)
        sys.stdout.flush()

    def desktop_notify(self, task: Dict[str, Any]) -> None:
        """Attempt to send a desktop notification via notify-send."""
        if not self._check_notify_send():
            return

        title = task.get("title", "Untitled")
        body = title
        if task.get("due_at"):
            body += f"\nDue: {task['due_at']}"
        if task.get("description"):
            body += f"\n{task['description']}"

        try:
            subprocess.run(
                ["notify-send", self.app_name, body],
                check=False,
                timeout=5,
                capture_output=True,
            )
        except (OSError, subprocess.TimeoutExpired):
            pass

    def _check_notify_send(self) -> bool:
        """Check once whether notify-send is available on the system."""
        if self._has_notify_send is None:
            self._has_notify_send = shutil.which("notify-send") is not None
        return self._has_notify_send
