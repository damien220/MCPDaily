"""Unit tests for Phase 2 tools: Search, Organize, Info, History, Undo, Config."""

from __future__ import annotations

import tempfile
from pathlib import Path
from datetime import datetime, timezone

import pytest

from core.models import MCPRequest, MCPResponse

from LocalFileHandler.config import Config, NamingConfig
from LocalFileHandler.history import Operation, OperationLog
from LocalFileHandler.naming import CategoryMap, NameFormatter
from LocalFileHandler.tools.config_tool import ConfigTool
from LocalFileHandler.tools.history_tool import HistoryTool
from LocalFileHandler.tools.info import InfoTool
from LocalFileHandler.tools.organize import OrganizeTool
from LocalFileHandler.tools.search import SearchTool
from LocalFileHandler.tools.undo import UndoTool


def make_request(tool: str, payload: dict, req_id: str = "t1") -> MCPRequest:
    return MCPRequest(id=req_id, tool=tool, payload=payload)


@pytest.fixture
def workspace(tmp_path):
    ws = tmp_path / "workspace"
    ws.mkdir()
    return ws


@pytest.fixture
def log(workspace):
    return OperationLog(log_path=workspace / ".history" / "operations.jsonl")


@pytest.fixture
def formatter(workspace):
    return NameFormatter(
        workspace=workspace,
        date_prefix=False,
        auto_categorize=True,
        normalize_extensions=True,
    )


@pytest.fixture
def category_map():
    return CategoryMap()


@pytest.fixture
def config(workspace):
    nc = NamingConfig()
    return Config(workspace_path=workspace, naming=nc)


# ── SearchTool ────────────────────────────────────────────────────────────────


class TestSearchTool:
    def test_find_by_name(self, workspace):
        (workspace / "report.txt").write_text("report content")
        (workspace / "notes.txt").write_text("notes content")
        tool = SearchTool(workspace=workspace)
        resp = tool.handle(make_request("searchtool", {"query": "report"}))
        assert resp.is_success()
        assert resp.result["count"] == 1
        assert "report.txt" in resp.result["results"][0]["name"]

    def test_find_by_extension(self, workspace):
        (workspace / "a.md").write_text("")
        (workspace / "b.txt").write_text("")
        (workspace / "c.md").write_text("")
        tool = SearchTool(workspace=workspace)
        resp = tool.handle(make_request("searchtool", {"type": "md"}))
        assert resp.is_success()
        assert resp.result["count"] == 2

    def test_find_by_regex(self, workspace):
        (workspace / "report-2026.txt").write_text("")
        (workspace / "notes.txt").write_text("")
        tool = SearchTool(workspace=workspace)
        resp = tool.handle(
            make_request("searchtool", {"query": r"report-\d{4}", "regex": True})
        )
        assert resp.is_success()
        assert resp.result["count"] == 1

    def test_find_no_results(self, workspace):
        (workspace / "file.txt").write_text("")
        tool = SearchTool(workspace=workspace)
        resp = tool.handle(make_request("searchtool", {"query": "xyzabc"}))
        assert resp.is_success()
        assert resp.result["count"] == 0

    def test_path_traversal_rejected(self, workspace):
        tool = SearchTool(workspace=workspace)
        resp = tool.handle(make_request("searchtool", {"path": "../../"}))
        assert not resp.is_success()

    def test_skips_hidden_dirs(self, workspace):
        trash = workspace / ".trash"
        trash.mkdir()
        (trash / "old.txt").write_text("old")
        (workspace / "visible.txt").write_text("visible")
        tool = SearchTool(workspace=workspace)
        resp = tool.handle(make_request("searchtool", {"query": "old"}))
        assert resp.is_success()
        assert resp.result["count"] == 0

    def test_size_filter(self, workspace):
        (workspace / "small.txt").write_bytes(b"x" * 10)
        (workspace / "large.txt").write_bytes(b"x" * 1000)
        tool = SearchTool(workspace=workspace)
        resp = tool.handle(make_request("searchtool", {"min_size": 500}))
        assert resp.is_success()
        assert resp.result["count"] == 1
        assert "large.txt" in resp.result["results"][0]["name"]

    def test_search_recursive(self, workspace):
        sub = workspace / "sub"
        sub.mkdir()
        (sub / "deep.txt").write_text("")
        tool = SearchTool(workspace=workspace)
        resp = tool.handle(make_request("searchtool", {"query": "deep"}))
        assert resp.is_success()
        assert resp.result["count"] == 1


# ── OrganizeTool ──────────────────────────────────────────────────────────────


class TestOrganizeTool:
    def test_dry_run_no_changes(self, workspace, formatter, log):
        (workspace / "My Report.TXT").write_text("content")
        tool = OrganizeTool(workspace=workspace, formatter=formatter, operation_log=log)
        resp = tool.handle(make_request("organizetool", {"path": ".", "dry_run": True}))
        assert resp.is_success()
        assert resp.result["dry_run"] is True
        # File still exists at original location
        assert (workspace / "My Report.TXT").exists()

    def test_execute_reorganizes(self, workspace, formatter, log):
        (workspace / "photo.PNG").write_text("")
        tool = OrganizeTool(workspace=workspace, formatter=formatter, operation_log=log)
        resp = tool.handle(make_request("organizetool", {"path": ".", "dry_run": False}))
        assert resp.is_success()
        assert resp.result["executed"] >= 1
        # File moved to images/ (auto-categorize) and extension normalized
        assert not (workspace / "photo.PNG").exists()

    def test_already_compliant_skipped(self, workspace, formatter, log):
        docs = workspace / "documents"
        docs.mkdir()
        (docs / "my-doc.txt").write_text("")
        tool = OrganizeTool(workspace=workspace, formatter=formatter, operation_log=log)
        resp = tool.handle(make_request("organizetool", {"path": ".", "dry_run": False}))
        assert resp.is_success()
        # Already in the right place, nothing executed
        assert resp.result["skipped"] >= 1

    def test_logs_undo_data(self, workspace, formatter, log):
        (workspace / "unorganized.PNG").write_text("")
        tool = OrganizeTool(workspace=workspace, formatter=formatter, operation_log=log)
        tool.handle(make_request("organizetool", {"path": ".", "dry_run": False}))
        ops = log.all_operations()
        assert len(ops) == 1
        assert ops[0].undo_data["action"] == "undo_organize"

    def test_path_traversal_rejected(self, workspace, formatter, log):
        tool = OrganizeTool(workspace=workspace, formatter=formatter, operation_log=log)
        resp = tool.handle(make_request("organizetool", {"path": "../../"}))
        assert not resp.is_success()


# ── InfoTool ──────────────────────────────────────────────────────────────────


class TestInfoTool:
    def test_file_info(self, workspace):
        f = workspace / "test.py"
        f.write_text("print('hi')")
        tool = InfoTool(workspace=workspace)
        resp = tool.handle(make_request("infotool", {"path": "test.py"}))
        assert resp.is_success()
        assert resp.result["type"] == "file"
        assert resp.result["extension"] == ".py"
        assert resp.result["size_bytes"] > 0
        assert resp.result["mime_type"] == "text/x-python"
        assert "md5" in resp.result
        assert "modified" in resp.result
        assert "permissions" in resp.result

    def test_directory_info(self, workspace):
        sub = workspace / "subdir"
        sub.mkdir()
        (sub / "a.txt").write_text("a")
        (sub / "b.txt").write_text("b")
        tool = InfoTool(workspace=workspace)
        resp = tool.handle(make_request("infotool", {"path": "subdir"}))
        assert resp.is_success()
        assert resp.result["type"] == "directory"
        assert resp.result["file_count"] == 2
        assert resp.result["dir_count"] == 0

    def test_skip_hash(self, workspace):
        (workspace / "large.bin").write_bytes(b"0" * 100)
        tool = InfoTool(workspace=workspace)
        resp = tool.handle(make_request("infotool", {"path": "large.bin", "hash": False}))
        assert resp.is_success()
        assert "md5" not in resp.result

    def test_nonexistent_path(self, workspace):
        tool = InfoTool(workspace=workspace)
        resp = tool.handle(make_request("infotool", {"path": "ghost.txt"}))
        assert not resp.is_success()

    def test_path_traversal_rejected(self, workspace):
        tool = InfoTool(workspace=workspace)
        resp = tool.handle(make_request("infotool", {"path": "../../etc/passwd"}))
        assert not resp.is_success()

    def test_human_size(self):
        assert InfoTool._human_size(500) == "500.0 B"
        assert InfoTool._human_size(2048) == "2.0 KB"
        assert InfoTool._human_size(1024 * 1024) == "1.0 MB"


# ── HistoryTool ───────────────────────────────────────────────────────────────


class TestHistoryTool:
    def _make_op(self, tool="createfiletool", status="success") -> Operation:
        return Operation(
            tool=tool,
            status=status,
            payload={"name": "test"},
            result={"path": "test.txt"},
            undoable=True,
            undo_data={"action": "delete_file", "path": "/tmp/test.txt"},
        )

    def test_get_recent_empty(self, log):
        tool = HistoryTool(operation_log=log)
        resp = tool.handle(make_request("historytool", {"limit": 10}))
        assert resp.is_success()
        assert resp.result["count"] == 0

    def test_get_recent(self, log):
        for i in range(3):
            log.record(self._make_op())
        tool = HistoryTool(operation_log=log)
        resp = tool.handle(make_request("historytool", {"limit": 10}))
        assert resp.is_success()
        assert resp.result["count"] == 3

    def test_filter_by_tool(self, log):
        log.record(self._make_op(tool="createfiletool"))
        log.record(self._make_op(tool="deletetool"))
        tool = HistoryTool(operation_log=log)
        resp = tool.handle(make_request("historytool", {"tool": "deletetool"}))
        assert resp.is_success()
        assert resp.result["count"] == 1
        assert resp.result["operations"][0]["tool"] == "deletetool"

    def test_filter_by_status(self, log):
        log.record(self._make_op(status="success"))
        log.record(self._make_op(status="error"))
        tool = HistoryTool(operation_log=log)
        resp = tool.handle(make_request("historytool", {"status": "error"}))
        assert resp.is_success()
        assert resp.result["count"] == 1

    def test_get_by_id(self, log):
        op = self._make_op()
        log.record(op)
        tool = HistoryTool(operation_log=log)
        resp = tool.handle(make_request("historytool", {"id": op.id}))
        assert resp.is_success()
        assert resp.result["operation"]["id"] == op.id

    def test_get_by_missing_id(self, log):
        tool = HistoryTool(operation_log=log)
        resp = tool.handle(make_request("historytool", {"id": "nonexistent"}))
        assert not resp.is_success()


# ── OperationLog ──────────────────────────────────────────────────────────────


class TestOperationLog:
    def test_record_and_read(self, log):
        op = Operation(
            tool="createfiletool",
            status="success",
            payload={"name": "test"},
            result={},
            undoable=True,
            undo_data={"action": "delete_file", "path": "/tmp/t.txt"},
        )
        log.record(op)
        ops = log.all_operations()
        assert len(ops) == 1
        assert ops[0].tool == "createfiletool"

    def test_mark_undone(self, log):
        op = Operation(
            tool="createfiletool",
            status="success",
            payload={},
            result={},
            undoable=True,
            undo_data={"action": "delete_file", "path": "/tmp/t.txt"},
        )
        log.record(op)
        assert log.mark_undone(op.id)
        assert log.all_operations()[0].undone is True

    def test_last_undoable(self, log):
        op1 = Operation(
            tool="createfiletool",
            status="success",
            payload={},
            result={},
            undoable=True,
            undo_data={"action": "delete_file", "path": "/tmp/a.txt"},
        )
        op2 = Operation(
            tool="createfiletool",
            status="success",
            payload={},
            result={},
            undoable=True,
            undo_data={"action": "delete_file", "path": "/tmp/b.txt"},
        )
        log.record(op1)
        log.record(op2)
        last = log.last_undoable()
        assert last is not None
        assert last.id == op2.id


# ── UndoTool ──────────────────────────────────────────────────────────────────


class TestUndoTool:
    def test_undo_create_file(self, workspace, log):
        # Simulate a createfiletool operation
        target = workspace / "to-delete.txt"
        target.write_text("temp")
        op = Operation(
            tool="createfiletool",
            status="success",
            payload={},
            result={},
            undoable=True,
            undo_data={"action": "delete_file", "path": str(target)},
        )
        log.record(op)

        tool = UndoTool(workspace=workspace, operation_log=log)
        resp = tool.handle(make_request("undotool", {"steps": 1}))
        assert resp.is_success()
        assert resp.result["undone_count"] == 1
        assert not target.exists()

    def test_undo_rename(self, workspace, log):
        original = workspace / "original.txt"
        renamed = workspace / "renamed.txt"
        renamed.write_text("content")
        op = Operation(
            tool="renametool",
            status="success",
            payload={},
            result={},
            undoable=True,
            undo_data={
                "action": "rename",
                "from_path": str(renamed),
                "to_path": str(original),
            },
        )
        log.record(op)
        tool = UndoTool(workspace=workspace, operation_log=log)
        resp = tool.handle(make_request("undotool", {"steps": 1}))
        assert resp.is_success()
        assert original.exists()
        assert not renamed.exists()

    def test_undo_restore_from_trash(self, workspace, log):
        trash_dir = workspace / ".trash"
        trash_dir.mkdir()
        trash_item = trash_dir / "20260101_file.txt"
        trash_item.write_text("restored")
        original = workspace / "file.txt"
        op = Operation(
            tool="deletetool",
            status="success",
            payload={},
            result={},
            undoable=True,
            undo_data={
                "action": "restore_from_trash",
                "trash_path": str(trash_item),
                "original_path": str(original),
            },
        )
        log.record(op)
        tool = UndoTool(workspace=workspace, operation_log=log)
        resp = tool.handle(make_request("undotool", {"steps": 1}))
        assert resp.is_success()
        assert original.exists()
        assert original.read_text() == "restored"

    def test_preview_does_not_execute(self, workspace, log):
        target = workspace / "kept.txt"
        target.write_text("keep me")
        op = Operation(
            tool="createfiletool",
            status="success",
            payload={},
            result={},
            undoable=True,
            undo_data={"action": "delete_file", "path": str(target)},
        )
        log.record(op)
        tool = UndoTool(workspace=workspace, operation_log=log)
        resp = tool.handle(make_request("undotool", {"steps": 1, "preview": True}))
        assert resp.is_success()
        assert resp.result["undone_count"] == 0
        assert target.exists()  # file not deleted in preview mode

    def test_empty_history(self, workspace, log):
        tool = UndoTool(workspace=workspace, operation_log=log)
        resp = tool.handle(make_request("undotool", {"steps": 1}))
        assert not resp.is_success()

    def test_undo_marks_operation_as_undone(self, workspace, log):
        target = workspace / "file.txt"
        target.write_text("x")
        op = Operation(
            tool="createfiletool",
            status="success",
            payload={},
            result={},
            undoable=True,
            undo_data={"action": "delete_file", "path": str(target)},
        )
        log.record(op)
        tool = UndoTool(workspace=workspace, operation_log=log)
        tool.handle(make_request("undotool", {"steps": 1}))
        # The operation should now be marked undone
        assert log.all_operations()[0].undone is True
        # Should no longer appear in undoable stack
        assert log.last_undoable() is None


# ── ConfigTool ────────────────────────────────────────────────────────────────


class TestConfigTool:
    def test_get_config(self, config, formatter, category_map):
        tool = ConfigTool(config=config, formatter=formatter, category_map=category_map)
        resp = tool.handle(make_request("configtool", {"action": "get"}))
        assert resp.is_success()
        assert "naming" in resp.result
        assert "date_prefix" in resp.result["naming"]

    def test_set_date_prefix(self, config, formatter, category_map):
        tool = ConfigTool(config=config, formatter=formatter, category_map=category_map)
        resp = tool.handle(
            make_request("configtool", {"action": "set", "values": {"date_prefix": False}})
        )
        assert resp.is_success()
        assert resp.result["current"]["date_prefix"] is False
        # Formatter should be updated too
        assert formatter.date_prefix_enabled is False

    def test_set_invalid_field(self, config, formatter, category_map):
        tool = ConfigTool(config=config, formatter=formatter, category_map=category_map)
        resp = tool.handle(
            make_request("configtool", {"action": "set", "values": {"unknown_key": True}})
        )
        assert resp.is_success()  # still succeeds but reports error
        assert "errors" in resp.result

    def test_reset_config(self, config, formatter, category_map):
        # Create the tool first so it captures the startup defaults
        tool = ConfigTool(config=config, formatter=formatter, category_map=category_map)
        # Change a value via the set action, then reset
        tool.handle(make_request("configtool", {"action": "set", "values": {"date_prefix": False}}))
        assert config.naming.date_prefix is False
        resp = tool.handle(make_request("configtool", {"action": "reset"}))
        assert resp.is_success()
        assert resp.result["current"]["date_prefix"] is True  # back to startup default

    def test_list_categories(self, config, formatter, category_map):
        tool = ConfigTool(config=config, formatter=formatter, category_map=category_map)
        resp = tool.handle(make_request("configtool", {"action": "categories"}))
        assert resp.is_success()
        assert "documents" in resp.result["categories"]
        assert resp.result["total_extensions"] > 0

    def test_add_category(self, config, formatter, category_map):
        tool = ConfigTool(config=config, formatter=formatter, category_map=category_map)
        resp = tool.handle(
            make_request(
                "configtool",
                {"action": "add_category", "extension": ".custom", "category": "my_cat"},
            )
        )
        assert resp.is_success()
        assert category_map.get_category(".custom") == "my_cat"

    def test_unknown_action(self, config, formatter, category_map):
        tool = ConfigTool(config=config, formatter=formatter, category_map=category_map)
        resp = tool.handle(make_request("configtool", {"action": "invalid"}))
        assert not resp.is_success()
