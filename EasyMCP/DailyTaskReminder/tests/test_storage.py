"""Tests for DailyTaskReminder.storage module."""

import json
import shutil
import tempfile
from pathlib import Path

from DailyTaskReminder.storage import TaskStorage


def make_storage() -> tuple[TaskStorage, Path]:
    """Create a TaskStorage backed by a temp directory."""
    tmpdir = Path(tempfile.mkdtemp())
    storage = TaskStorage(path=tmpdir / "tasks.json")
    return storage, tmpdir


def test_add_and_list():
    storage, tmpdir = make_storage()
    try:
        t1 = storage.add_task("Buy groceries", description="Milk, eggs, bread",
                              due_at="2026-02-14T09:00:00", remind_at="2026-02-14T08:30:00")
        t2 = storage.add_task("Finish report", due_at="2026-02-15T17:00:00")
        t3 = storage.add_task("Call dentist")

        assert t1["id"] and t2["id"] and t3["id"]
        print(f"[OK] Added 3 tasks: {t1['id']}, {t2['id']}, {t3['id']}")

        all_tasks = storage.list_tasks("all")
        assert len(all_tasks) == 3, f"Expected 3, got {len(all_tasks)}"
        print(f"[OK] list_tasks('all') returned {len(all_tasks)} tasks")

        pending = storage.list_tasks("pending")
        assert len(pending) == 3
        print(f"[OK] list_tasks('pending') returned {len(pending)} tasks")
    finally:
        shutil.rmtree(tmpdir)


def test_get_task_by_full_and_prefix_id():
    storage, tmpdir = make_storage()
    try:
        t1 = storage.add_task("Task A")
        t2 = storage.add_task("Task B")

        # Full ID lookup
        fetched = storage.get_task(t1["id"])
        assert fetched is not None and fetched["title"] == "Task A"
        print(f"[OK] get_task(full_id) found: {fetched['title']}")

        # Prefix lookup
        prefix = t2["id"][:4]
        fetched2 = storage.get_task(prefix)
        assert fetched2 is not None and fetched2["title"] == "Task B"
        print(f"[OK] get_task(prefix={prefix}) found: {fetched2['title']}")
    finally:
        shutil.rmtree(tmpdir)


def test_complete_task():
    storage, tmpdir = make_storage()
    try:
        t1 = storage.add_task("Do laundry")
        completed = storage.complete_task(t1["id"])
        assert completed is not None and completed["status"] == "completed"
        print(f"[OK] complete_task: {completed['title']} -> {completed['status']}")

        completed_list = storage.list_tasks("completed")
        assert len(completed_list) == 1
        print(f"[OK] list_tasks('completed') returned {len(completed_list)} task")
    finally:
        shutil.rmtree(tmpdir)


def test_delete_task():
    storage, tmpdir = make_storage()
    try:
        t1 = storage.add_task("Task to keep")
        t2 = storage.add_task("Task to delete")

        deleted = storage.delete_task(t2["id"])
        assert deleted is not None and deleted["title"] == "Task to delete"

        remaining = storage.list_tasks("all")
        assert len(remaining) == 1
        print(f"[OK] delete_task: removed \"{deleted['title']}\", {len(remaining)} remaining")
    finally:
        shutil.rmtree(tmpdir)


def test_persistence():
    tmpdir = Path(tempfile.mkdtemp())
    try:
        path = tmpdir / "tasks.json"
        storage1 = TaskStorage(path=path)
        storage1.add_task("Persistent task")

        # Create a new storage instance pointing at the same file
        storage2 = TaskStorage(path=path)
        reloaded = storage2.list_tasks("all")
        assert len(reloaded) == 1 and reloaded[0]["title"] == "Persistent task"
        print(f"[OK] Persistence: reloaded {len(reloaded)} tasks from disk")

        # Verify raw JSON is valid
        with open(path, encoding="utf-8") as f:
            data = json.load(f)
        assert isinstance(data, list) and len(data) == 1
        print(f"[OK] JSON file is valid with {len(data)} entries")
    finally:
        shutil.rmtree(tmpdir)


def test_due_reminders():
    storage, tmpdir = make_storage()
    try:
        # Future reminder — should not fire
        storage.add_task("Future task", remind_at="2099-01-01T00:00:00")
        due = storage.get_due_reminders()
        assert len(due) == 0
        print(f"[OK] get_due_reminders: {len(due)} (none due yet)")

        # Past reminder — should fire
        storage.add_task("Past reminder", remind_at="2020-01-01T00:00:00")
        due2 = storage.get_due_reminders()
        assert len(due2) == 1 and due2[0]["title"] == "Past reminder"
        print(f"[OK] get_due_reminders: {len(due2)} fired for past remind_at")

        # Should not fire again (already notified)
        due3 = storage.get_due_reminders()
        assert len(due3) == 0
        print(f"[OK] get_due_reminders: {len(due3)} (already notified, no repeat)")
    finally:
        shutil.rmtree(tmpdir)


def test_get_nonexistent_task():
    storage, tmpdir = make_storage()
    try:
        result = storage.get_task("nonexistent")
        assert result is None
        print("[OK] get_task returns None for nonexistent ID")
    finally:
        shutil.rmtree(tmpdir)


if __name__ == "__main__":
    test_add_and_list()
    test_get_task_by_full_and_prefix_id()
    test_complete_task()
    test_delete_task()
    test_persistence()
    test_due_reminders()
    test_get_nonexistent_task()
    print("\nAll tests passed.")
