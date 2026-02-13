"""End-to-end tests for the interactive CLI and notifier."""

import io
import os
import shutil
import sys
import tempfile
import threading
import time
from pathlib import Path

from core.router import ToolRouter

from DailyTaskReminder.interactive_cli import InteractiveCLI, _normalize_datetime, _parse_args_with_flags
from DailyTaskReminder.notifier import Notifier
from DailyTaskReminder.storage import TaskStorage
from DailyTaskReminder.tools import (
    AddTaskTool,
    CheckRemindersTool,
    CompleteTaskTool,
    DeleteTaskTool,
    ListTasksTool,
)


def _setup() -> tuple[TaskStorage, ToolRouter, Path]:
    tmpdir = Path(tempfile.mkdtemp())
    storage = TaskStorage(path=tmpdir / "tasks.json")
    router = ToolRouter()
    for tool in [AddTaskTool(storage), ListTasksTool(storage),
                 CompleteTaskTool(storage), DeleteTaskTool(storage),
                 CheckRemindersTool(storage)]:
        router.register(tool)
    return storage, router, tmpdir


def _run_cli(router: ToolRouter, commands: str) -> str:
    """Run the REPL with simulated stdin and capture stdout."""
    old_stdin, old_stdout = sys.stdin, sys.stdout
    sys.stdin = io.StringIO(commands)
    captured = io.StringIO()
    sys.stdout = captured

    # Use a very long poll interval so bg thread doesn't interfere
    old_poll = os.environ.get("DTR_POLL_INTERVAL")
    os.environ["DTR_POLL_INTERVAL"] = "9999"

    try:
        cli = InteractiveCLI(router, Notifier())
        cli.run()
    finally:
        sys.stdin, sys.stdout = old_stdin, old_stdout
        if old_poll is not None:
            os.environ["DTR_POLL_INTERVAL"] = old_poll
        else:
            os.environ.pop("DTR_POLL_INTERVAL", None)

    return captured.getvalue()


# --- Tests ---

def test_add_list_complete_delete_flow():
    storage, router, tmpdir = _setup()
    try:
        t1 = storage.add_task("Task One", due_at="2026-03-01T10:00:00")
        t2 = storage.add_task("Task Two")

        output = _run_cli(router, f"list\ncomplete {t1['id'][:4]}\ndelete {t2['id'][:4]}\nlist --filter all\nquit\n")
        assert "Task One" in output
        assert "Task Two" in output
        assert "Completed:" in output
        assert "Deleted:" in output
        print("[OK] add/list/complete/delete flow works")
    finally:
        shutil.rmtree(tmpdir)


def test_empty_storage():
    _, router, tmpdir = _setup()
    try:
        output = _run_cli(router, "list\nquit\n")
        assert "No pending tasks" in output
        print("[OK] Empty storage shows 'No pending tasks'")
    finally:
        shutil.rmtree(tmpdir)


def test_unknown_command():
    _, router, tmpdir = _setup()
    try:
        output = _run_cli(router, "foobar\nquit\n")
        assert "Unknown command" in output
        print("[OK] Unknown command handled")
    finally:
        shutil.rmtree(tmpdir)


def test_missing_args():
    _, router, tmpdir = _setup()
    try:
        output = _run_cli(router, "add\ncomplete\ndelete\nquit\n")
        assert "Usage: add" in output
        assert "Usage: complete" in output
        assert "Usage: delete" in output
        print("[OK] Missing arguments show usage hints")
    finally:
        shutil.rmtree(tmpdir)


def test_notfound_errors():
    _, router, tmpdir = _setup()
    try:
        output = _run_cli(router, "complete xxxx\ndelete yyyy\nquit\n")
        assert "not found" in output
        print("[OK] Not-found errors displayed correctly")
    finally:
        shutil.rmtree(tmpdir)


def test_normalize_datetime():
    assert _normalize_datetime("2026-03-01 14:30") == "2026-03-01T14:30:00"
    assert _normalize_datetime("2026-03-01T14:30:00") == "2026-03-01T14:30:00"
    assert _normalize_datetime("2026-03-01") == "2026-03-01T00:00:00"
    print("[OK] _normalize_datetime handles all formats")


def test_parse_args_with_flags():
    title, opts = _parse_args_with_flags(
        ["Buy", "groceries", "--desc", "food items", "--due", "2026-03-01 09:00"],
        ("--desc", "--due", "--remind"),
    )
    assert title == "Buy groceries"
    assert opts["--desc"] == "food items"
    assert opts["--due"] == "2026-03-01 09:00"
    assert "--remind" not in opts
    print("[OK] _parse_args_with_flags extracts title and flags")


def test_reminder_background_thread():
    storage, router, tmpdir = _setup()
    try:
        storage.add_task("Past due task", remind_at="2020-01-01T00:00:00", due_at="2020-01-01T10:00:00")

        old_stdout = sys.stdout
        captured = io.StringIO()
        sys.stdout = captured

        notifier = Notifier()
        cli = InteractiveCLI(router, notifier)
        cli._stop_event = threading.Event()

        # Override poll interval to 1s
        import DailyTaskReminder.config as cfg
        old_interval = cfg.POLL_INTERVAL
        cfg.POLL_INTERVAL = 1

        bg = threading.Thread(target=cli._reminder_loop, daemon=True)
        bg.start()
        time.sleep(2.5)
        cli._stop_event.set()

        cfg.POLL_INTERVAL = old_interval
        sys.stdout = old_stdout

        output = captured.getvalue()
        assert "[REMINDER]" in output
        assert "Past due task" in output
        print("[OK] Background reminder thread fires notification")
    finally:
        shutil.rmtree(tmpdir)


if __name__ == "__main__":
    test_add_list_complete_delete_flow()
    test_empty_storage()
    test_unknown_command()
    test_missing_args()
    test_notfound_errors()
    test_normalize_datetime()
    test_parse_args_with_flags()
    test_reminder_background_thread()
    print("\nAll interactive tests passed.")
