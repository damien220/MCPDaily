"""Tests for DailyTaskReminder MCP tools."""

import shutil
import tempfile
from pathlib import Path

from core.models import MCPRequest

from DailyTaskReminder.storage import TaskStorage
from DailyTaskReminder.tools import (
    AddTaskTool,
    ListTasksTool,
    CompleteTaskTool,
    DeleteTaskTool,
    CheckRemindersTool,
)


def make_storage() -> tuple[TaskStorage, Path]:
    tmpdir = Path(tempfile.mkdtemp())
    return TaskStorage(path=tmpdir / "tasks.json"), tmpdir


def test_add_task_tool():
    storage, tmpdir = make_storage()
    try:
        tool = AddTaskTool(storage)

        # Success case
        req = MCPRequest(id="1", tool="addtask", payload={
            "title": "Buy milk",
            "description": "From the store",
            "due_at": "2026-02-14T09:00:00",
            "remind_at": "2026-02-14T08:30:00",
        })
        resp = tool(req)
        assert resp.is_success()
        assert resp.result["title"] == "Buy milk"
        assert resp.result["status"] == "pending"
        print(f"[OK] AddTaskTool success: {resp.result['id']}")

        # Missing title
        req2 = MCPRequest(id="2", tool="addtask", payload={})
        resp2 = tool(req2)
        assert not resp2.is_success()
        assert "title" in resp2.error
        print(f"[OK] AddTaskTool rejects missing title: {resp2.error}")
    finally:
        shutil.rmtree(tmpdir)


def test_list_tasks_tool():
    storage, tmpdir = make_storage()
    try:
        tool = ListTasksTool(storage)
        add = AddTaskTool(storage)

        add(MCPRequest(id="1", tool="addtask", payload={"title": "Task A"}))
        add(MCPRequest(id="2", tool="addtask", payload={"title": "Task B"}))

        # List pending
        resp = tool(MCPRequest(id="3", tool="listtasks", payload={}))
        assert resp.is_success() and resp.result["count"] == 2
        print(f"[OK] ListTasksTool pending: {resp.result['count']} tasks")

        # Invalid filter
        resp2 = tool(MCPRequest(id="4", tool="listtasks", payload={"filter": "bad"}))
        assert not resp2.is_success()
        print(f"[OK] ListTasksTool rejects invalid filter: {resp2.error}")
    finally:
        shutil.rmtree(tmpdir)


def test_complete_task_tool():
    storage, tmpdir = make_storage()
    try:
        add = AddTaskTool(storage)
        complete = CompleteTaskTool(storage)

        r = add(MCPRequest(id="1", tool="addtask", payload={"title": "Do stuff"}))
        task_id = r.result["id"]

        resp = complete(MCPRequest(id="2", tool="completetask", payload={"task_id": task_id}))
        assert resp.is_success() and resp.result["status"] == "completed"
        print(f"[OK] CompleteTaskTool success: {task_id}")

        # Not found
        resp2 = complete(MCPRequest(id="3", tool="completetask", payload={"task_id": "nope"}))
        assert not resp2.is_success()
        print(f"[OK] CompleteTaskTool not found: {resp2.error}")

        # Missing task_id
        resp3 = complete(MCPRequest(id="4", tool="completetask", payload={}))
        assert not resp3.is_success()
        print(f"[OK] CompleteTaskTool missing task_id: {resp3.error}")
    finally:
        shutil.rmtree(tmpdir)


def test_delete_task_tool():
    storage, tmpdir = make_storage()
    try:
        add = AddTaskTool(storage)
        delete = DeleteTaskTool(storage)

        r = add(MCPRequest(id="1", tool="addtask", payload={"title": "Temp task"}))
        task_id = r.result["id"]

        resp = delete(MCPRequest(id="2", tool="deletetask", payload={"task_id": task_id}))
        assert resp.is_success()
        assert resp.result["deleted"]["id"] == task_id
        print(f"[OK] DeleteTaskTool success: removed {task_id}")

        # Verify it's gone
        list_tool = ListTasksTool(storage)
        lr = list_tool(MCPRequest(id="3", tool="listtasks", payload={"filter": "all"}))
        assert lr.result["count"] == 0
        print("[OK] DeleteTaskTool verified: 0 tasks remaining")
    finally:
        shutil.rmtree(tmpdir)


def test_check_reminders_tool():
    storage, tmpdir = make_storage()
    try:
        add = AddTaskTool(storage)
        check = CheckRemindersTool(storage)

        # Future reminder — should not fire
        add(MCPRequest(id="1", tool="addtask", payload={
            "title": "Future", "remind_at": "2099-01-01T00:00:00",
        }))
        resp = check(MCPRequest(id="2", tool="checkreminders", payload={}))
        assert resp.is_success() and resp.result["count"] == 0
        print("[OK] CheckRemindersTool: 0 due (future)")

        # Past reminder — should fire
        add(MCPRequest(id="3", tool="addtask", payload={
            "title": "Overdue", "remind_at": "2020-01-01T00:00:00",
        }))
        resp2 = check(MCPRequest(id="4", tool="checkreminders", payload={}))
        assert resp2.is_success() and resp2.result["count"] == 1
        print(f"[OK] CheckRemindersTool: 1 due (past)")

        # Should not repeat
        resp3 = check(MCPRequest(id="5", tool="checkreminders", payload={}))
        assert resp3.result["count"] == 0
        print("[OK] CheckRemindersTool: 0 due (already notified)")
    finally:
        shutil.rmtree(tmpdir)


if __name__ == "__main__":
    test_add_task_tool()
    test_list_tasks_tool()
    test_complete_task_tool()
    test_delete_task_tool()
    test_check_reminders_tool()
    print("\nAll tool tests passed.")
