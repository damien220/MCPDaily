"""Interactive CLI (REPL) for DailyTaskReminder."""

from __future__ import annotations

import shlex
import threading
import time
from typing import Any, Dict, List

from core.models import MCPRequest
from core.router import ToolRouter

from . import config
from .notifier import Notifier

# ANSI helpers
_BOLD = "\033[1m"
_DIM = "\033[2m"
_GREEN = "\033[32m"
_RED = "\033[31m"
_CYAN = "\033[36m"
_YELLOW = "\033[33m"
_RESET = "\033[0m"

HELP_TEXT = f"""\
{_BOLD}Available commands:{_RESET}

  {_CYAN}add{_RESET} <title> [--desc "..."] [--due "YYYY-MM-DD HH:MM"] [--remind "YYYY-MM-DD HH:MM"]
      Add a new task.

  {_CYAN}list{_RESET} [--filter pending|completed|overdue|all]
      List tasks (default: pending).

  {_CYAN}complete{_RESET} <task_id>
      Mark a task as completed.

  {_CYAN}delete{_RESET} <task_id>
      Delete a task.

  {_CYAN}help{_RESET}
      Show this help message.

  {_CYAN}quit{_RESET} / {_CYAN}exit{_RESET}
      Exit the application.
"""


class InteractiveCLI:
    """REPL interface that dispatches commands through the MCP ToolRouter."""

    def __init__(self, router: ToolRouter, notifier: Notifier | None = None) -> None:
        self.router = router
        self.notifier = notifier or Notifier()
        self._request_counter = 0
        self._stop_event = threading.Event()

    # --- public ---

    def run(self) -> None:
        """Start the REPL with background reminder thread."""
        print(f"{_BOLD}{config.APP_NAME} v{config.APP_VERSION}{_RESET} — type 'help' for commands\n")

        bg_thread = threading.Thread(target=self._reminder_loop, daemon=True)
        bg_thread.start()

        try:
            self._repl()
        except KeyboardInterrupt:
            print()
        finally:
            self._stop_event.set()
            print("Goodbye!")

    # --- REPL ---

    def _repl(self) -> None:
        while not self._stop_event.is_set():
            try:
                line = input(f"{_BOLD}>{_RESET} ").strip()
            except EOFError:
                break
            if not line:
                continue

            try:
                tokens = shlex.split(line)
            except ValueError as exc:
                print(f"{_RED}Parse error: {exc}{_RESET}")
                continue

            command = tokens[0].lower()

            if command in ("quit", "exit"):
                break
            elif command == "help":
                print(HELP_TEXT)
            elif command == "add":
                self._handle_add(tokens[1:])
            elif command == "list":
                self._handle_list(tokens[1:])
            elif command == "complete":
                self._handle_complete(tokens[1:])
            elif command == "delete":
                self._handle_delete(tokens[1:])
            else:
                print(f"{_RED}Unknown command: '{command}'. Type 'help' for available commands.{_RESET}")

    # --- command handlers ---

    def _handle_add(self, args: List[str]) -> None:
        title, opts = _parse_args_with_flags(args, ("--desc", "--due", "--remind"))
        if not title:
            print(f"{_RED}Usage: add <title> [--desc \"...\"] [--due \"YYYY-MM-DD HH:MM\"] [--remind \"YYYY-MM-DD HH:MM\"]{_RESET}")
            return

        payload: Dict[str, Any] = {"title": title}
        if opts.get("--desc"):
            payload["description"] = opts["--desc"]
        if opts.get("--due"):
            payload["due_at"] = _normalize_datetime(opts["--due"])
        if opts.get("--remind"):
            payload["remind_at"] = _normalize_datetime(opts["--remind"])

        resp = self._invoke("addtask", payload)
        if resp.is_success():
            task = resp.result
            due_str = f"  due: {task['due_at']}" if task.get("due_at") else ""
            print(f"{_GREEN}Task created:{_RESET} [{task['id']}] {task['title']}{due_str}")
        else:
            print(f"{_RED}Error: {resp.error}{_RESET}")

    def _handle_list(self, args: List[str]) -> None:
        _, opts = _parse_args_with_flags(args, ("--filter",))
        status_filter = opts.get("--filter", "pending")

        resp = self._invoke("listtasks", {"filter": status_filter})
        if not resp.is_success():
            print(f"{_RED}Error: {resp.error}{_RESET}")
            return

        tasks: List[Dict[str, Any]] = resp.result["tasks"]
        count = resp.result["count"]
        label = status_filter.capitalize()

        if count == 0:
            print(f"{_DIM}No {status_filter} tasks.{_RESET}")
            return

        print(f"{_BOLD}{label} tasks ({count}):{_RESET}")
        for t in tasks:
            status_tag = ""
            if status_filter == "all":
                if t["status"] == "completed":
                    status_tag = f"  {_DIM}[COMPLETED]{_RESET}"
                else:
                    status_tag = f"  {_CYAN}[PENDING]{_RESET}"

            due_str = ""
            if t.get("due_at"):
                due_str = f"  Due: {t['due_at']}"

            remind_str = ""
            if t.get("remind_at") and t["status"] == "pending":
                remind_str = f"  Remind: {t['remind_at']}"

            print(f"  [{t['id']}] {t['title']}{due_str}{remind_str}{status_tag}")

    def _handle_complete(self, args: List[str]) -> None:
        if not args:
            print(f"{_RED}Usage: complete <task_id>{_RESET}")
            return

        task_id = args[0]
        resp = self._invoke("completetask", {"task_id": task_id})
        if resp.is_success():
            task = resp.result
            print(f"{_GREEN}Completed:{_RESET} [{task['id']}] {task['title']}")
        else:
            print(f"{_RED}Error: {resp.error}{_RESET}")

    def _handle_delete(self, args: List[str]) -> None:
        if not args:
            print(f"{_RED}Usage: delete <task_id>{_RESET}")
            return

        task_id = args[0]
        resp = self._invoke("deletetask", {"task_id": task_id})
        if resp.is_success():
            task = resp.result["deleted"]
            print(f"{_GREEN}Deleted:{_RESET} [{task['id']}] {task['title']}")
        else:
            print(f"{_RED}Error: {resp.error}{_RESET}")

    # --- background reminder loop ---

    def _reminder_loop(self) -> None:
        """Periodically check for due reminders in a daemon thread."""
        while not self._stop_event.wait(timeout=config.POLL_INTERVAL):
            try:
                resp = self._invoke("checkreminders", {})
                if resp.is_success() and resp.result["count"] > 0:
                    for task in resp.result["tasks"]:
                        self.notifier.notify(task)
            except Exception:
                pass  # don't crash the background thread

    # --- helpers ---

    def _invoke(self, tool: str, payload: Dict[str, Any]) -> Any:
        """Build an MCPRequest and dispatch it through the router."""
        self._request_counter += 1
        req = MCPRequest(
            id=str(self._request_counter),
            tool=tool,
            payload=payload,
        )
        return self.router.route(req)


def _parse_args_with_flags(
    args: List[str], flags: tuple[str, ...]
) -> tuple[str, Dict[str, str]]:
    """Parse a list of tokens into a positional title and flag values.

    Returns (title_string, {flag: value}).
    Positional tokens that appear before any flag are joined as the title.
    """
    title_parts: List[str] = []
    opts: Dict[str, str] = {}
    i = 0
    while i < len(args):
        token = args[i]
        if token in flags:
            if i + 1 < len(args):
                opts[token] = args[i + 1]
                i += 2
            else:
                i += 1  # flag with no value, skip
        else:
            title_parts.append(token)
            i += 1
    return " ".join(title_parts), opts


def _normalize_datetime(value: str) -> str:
    """Convert 'YYYY-MM-DD HH:MM' to ISO format 'YYYY-MM-DDTHH:MM:00'.

    If the value already contains a 'T', return as-is.
    """
    value = value.strip()
    if "T" in value:
        return value
    # Handle "YYYY-MM-DD HH:MM" → "YYYY-MM-DDTHH:MM:00"
    if " " in value:
        parts = value.split(" ", 1)
        time_part = parts[1]
        if len(time_part) == 5:  # HH:MM
            time_part += ":00"
        return f"{parts[0]}T{time_part}"
    # Date only — append midnight
    return f"{value}T00:00:00"
