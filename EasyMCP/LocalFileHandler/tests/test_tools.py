"""Unit tests for all 6 MCP tools."""

import tempfile
from pathlib import Path

import pytest

from core.models import MCPRequest, MCPResponse

from LocalFileHandler.naming import CategoryMap, NameFormatter
from LocalFileHandler.tools.create_dir import CreateDirTool
from LocalFileHandler.tools.create_file import CreateFileTool
from LocalFileHandler.tools.delete import DeleteTool
from LocalFileHandler.tools.list_contents import ListContentsTool
from LocalFileHandler.tools.move import MoveTool
from LocalFileHandler.tools.rename import RenameTool


@pytest.fixture
def workspace(tmp_path):
    """Create a temporary workspace directory."""
    ws = tmp_path / "workspace"
    ws.mkdir()
    return ws


@pytest.fixture
def formatter(workspace):
    """Create a NameFormatter with date_prefix disabled for predictable tests."""
    return NameFormatter(
        workspace=workspace,
        date_prefix=False,
        auto_categorize=True,
        normalize_extensions=True,
    )


def make_request(tool: str, payload: dict, req_id: str = "test-1") -> MCPRequest:
    return MCPRequest(id=req_id, tool=tool, payload=payload)


# --- CreateFileTool ---


class TestCreateFileTool:
    def test_create_basic_file(self, workspace, formatter):
        tool = CreateFileTool(workspace=workspace, formatter=formatter)
        req = make_request("createfiletool", {"name": "hello", "type": "txt", "content": "Hello!"})
        resp = tool.handle(req)
        assert resp.is_success()
        assert "hello.txt" in resp.result["path"]
        # File actually exists
        assert Path(resp.result["absolute_path"]).read_text() == "Hello!"

    def test_create_md_auto_categorizes(self, workspace, formatter):
        tool = CreateFileTool(workspace=workspace, formatter=formatter)
        req = make_request("createfiletool", {"name": "notes", "type": "md", "content": "# Notes"})
        resp = tool.handle(req)
        assert resp.is_success()
        assert "documents" in resp.result["path"]

    def test_create_no_name(self, workspace, formatter):
        tool = CreateFileTool(workspace=workspace, formatter=formatter)
        req = make_request("createfiletool", {"type": "txt"})
        resp = tool.handle(req)
        assert not resp.is_success()
        assert "name" in resp.error.lower()

    def test_create_default_extension(self, workspace, formatter):
        tool = CreateFileTool(workspace=workspace, formatter=formatter)
        req = make_request("createfiletool", {"name": "readme"})
        resp = tool.handle(req)
        assert resp.is_success()
        assert ".txt" in resp.result["path"]

    def test_create_empty_content(self, workspace, formatter):
        tool = CreateFileTool(workspace=workspace, formatter=formatter)
        req = make_request("createfiletool", {"name": "empty", "type": "txt"})
        resp = tool.handle(req)
        assert resp.is_success()
        assert Path(resp.result["absolute_path"]).read_text() == ""


# --- CreateDirTool ---


class TestCreateDirTool:
    def test_create_basic_dir(self, workspace, formatter):
        tool = CreateDirTool(workspace=workspace, formatter=formatter)
        req = make_request("createdirtool", {"name": "My Project"})
        resp = tool.handle(req)
        assert resp.is_success()
        assert "my-project" in resp.result["path"]
        assert Path(resp.result["absolute_path"]).is_dir()

    def test_create_dir_in_projects(self, workspace, formatter):
        tool = CreateDirTool(workspace=workspace, formatter=formatter)
        req = make_request("createdirtool", {"name": "Alpha"})
        resp = tool.handle(req)
        assert resp.is_success()
        assert "projects" in resp.result["path"]

    def test_create_no_name(self, workspace, formatter):
        tool = CreateDirTool(workspace=workspace, formatter=formatter)
        req = make_request("createdirtool", {})
        resp = tool.handle(req)
        assert not resp.is_success()


# --- ListContentsTool ---


class TestListContentsTool:
    def test_list_empty(self, workspace):
        tool = ListContentsTool(workspace=workspace)
        req = make_request("listcontentstool", {"path": "."})
        resp = tool.handle(req)
        assert resp.is_success()
        assert resp.result["count"] == 0

    def test_list_with_files(self, workspace):
        (workspace / "file1.txt").write_text("a")
        (workspace / "file2.md").write_text("b")
        tool = ListContentsTool(workspace=workspace)
        req = make_request("listcontentstool", {"path": "."})
        resp = tool.handle(req)
        assert resp.is_success()
        assert resp.result["count"] == 2

    def test_list_recursive(self, workspace):
        sub = workspace / "sub"
        sub.mkdir()
        (sub / "nested.txt").write_text("nested")
        tool = ListContentsTool(workspace=workspace)
        req = make_request("listcontentstool", {"path": ".", "recursive": True})
        resp = tool.handle(req)
        assert resp.is_success()
        assert resp.result["count"] == 2  # sub dir + nested.txt

    def test_list_nonexistent(self, workspace):
        tool = ListContentsTool(workspace=workspace)
        req = make_request("listcontentstool", {"path": "nonexistent"})
        resp = tool.handle(req)
        assert not resp.is_success()

    def test_list_path_traversal(self, workspace):
        tool = ListContentsTool(workspace=workspace)
        req = make_request("listcontentstool", {"path": "../../"})
        resp = tool.handle(req)
        assert not resp.is_success()
        assert "outside" in resp.error.lower()

    def test_list_entry_metadata(self, workspace):
        (workspace / "test.py").write_text("print('hi')")
        tool = ListContentsTool(workspace=workspace)
        req = make_request("listcontentstool", {"path": "."})
        resp = tool.handle(req)
        entry = resp.result["entries"][0]
        assert entry["type"] == "file"
        assert entry["extension"] == ".py"
        assert entry["size"] > 0
        assert "modified" in entry


# --- RenameTool ---


class TestRenameTool:
    def test_rename_file(self, workspace, formatter):
        (workspace / "old.txt").write_text("content")
        tool = RenameTool(workspace=workspace, formatter=formatter)
        req = make_request("renametool", {"path": "old.txt", "new_name": "New Name"})
        resp = tool.handle(req)
        assert resp.is_success()
        assert "new-name" in resp.result["new_path"]
        assert not (workspace / "old.txt").exists()
        assert (workspace / "new-name.txt").exists()

    def test_rename_directory(self, workspace, formatter):
        (workspace / "old-dir").mkdir()
        tool = RenameTool(workspace=workspace, formatter=formatter)
        req = make_request("renametool", {"path": "old-dir", "new_name": "New Dir"})
        resp = tool.handle(req)
        assert resp.is_success()
        assert (workspace / "new-dir").is_dir()

    def test_rename_nonexistent(self, workspace, formatter):
        tool = RenameTool(workspace=workspace, formatter=formatter)
        req = make_request("renametool", {"path": "ghost.txt", "new_name": "new"})
        resp = tool.handle(req)
        assert not resp.is_success()

    def test_rename_conflict(self, workspace, formatter):
        (workspace / "a.txt").write_text("a")
        (workspace / "b.txt").write_text("b")
        tool = RenameTool(workspace=workspace, formatter=formatter)
        req = make_request("renametool", {"path": "a.txt", "new_name": "b"})
        resp = tool.handle(req)
        assert not resp.is_success()
        assert "exists" in resp.error.lower()

    def test_rename_missing_fields(self, workspace, formatter):
        tool = RenameTool(workspace=workspace, formatter=formatter)
        req = make_request("renametool", {"path": "a.txt"})
        resp = tool.handle(req)
        assert not resp.is_success()


# --- MoveTool ---


class TestMoveTool:
    def test_move_to_directory(self, workspace, formatter):
        (workspace / "file.txt").write_text("data")
        dest = workspace / "archive"
        dest.mkdir()
        tool = MoveTool(workspace=workspace, formatter=formatter)
        req = make_request("movetool", {"source": "file.txt", "destination": "archive/"})
        resp = tool.handle(req)
        assert resp.is_success()
        assert not (workspace / "file.txt").exists()
        assert (dest / "file.txt").exists()

    def test_move_nonexistent(self, workspace, formatter):
        tool = MoveTool(workspace=workspace, formatter=formatter)
        req = make_request("movetool", {"source": "ghost.txt", "destination": "archive/"})
        resp = tool.handle(req)
        assert not resp.is_success()

    def test_move_path_traversal(self, workspace, formatter):
        (workspace / "secret.txt").write_text("secret")
        tool = MoveTool(workspace=workspace, formatter=formatter)
        req = make_request("movetool", {"source": "secret.txt", "destination": "../../outside/"})
        resp = tool.handle(req)
        assert not resp.is_success()

    def test_move_missing_fields(self, workspace, formatter):
        tool = MoveTool(workspace=workspace, formatter=formatter)
        req = make_request("movetool", {"source": "file.txt"})
        resp = tool.handle(req)
        assert not resp.is_success()


# --- DeleteTool ---


class TestDeleteTool:
    def test_delete_to_trash(self, workspace):
        (workspace / "victim.txt").write_text("bye")
        tool = DeleteTool(workspace=workspace, trash_enabled=True, trash_dir=".trash")
        req = make_request("deletetool", {"path": "victim.txt", "confirm": True})
        resp = tool.handle(req)
        assert resp.is_success()
        assert resp.result["moved_to_trash"] is True
        assert not (workspace / "victim.txt").exists()
        # File should be in trash
        trash = workspace / ".trash"
        assert any("victim.txt" in f.name for f in trash.iterdir())

    def test_delete_permanent(self, workspace):
        (workspace / "perm.txt").write_text("gone")
        tool = DeleteTool(workspace=workspace, trash_enabled=False)
        req = make_request("deletetool", {"path": "perm.txt", "confirm": True})
        resp = tool.handle(req)
        assert resp.is_success()
        assert resp.result["moved_to_trash"] is False
        assert not (workspace / "perm.txt").exists()

    def test_delete_no_confirm(self, workspace):
        (workspace / "safe.txt").write_text("safe")
        tool = DeleteTool(workspace=workspace)
        req = make_request("deletetool", {"path": "safe.txt"})
        resp = tool.handle(req)
        assert not resp.is_success()
        assert "confirm" in resp.error.lower()
        assert (workspace / "safe.txt").exists()  # Not deleted

    def test_delete_nonexistent(self, workspace):
        tool = DeleteTool(workspace=workspace)
        req = make_request("deletetool", {"path": "ghost.txt", "confirm": True})
        resp = tool.handle(req)
        assert not resp.is_success()

    def test_delete_directory(self, workspace):
        d = workspace / "to-delete"
        d.mkdir()
        (d / "inner.txt").write_text("inner")
        tool = DeleteTool(workspace=workspace, trash_enabled=True, trash_dir=".trash")
        req = make_request("deletetool", {"path": "to-delete", "confirm": True})
        resp = tool.handle(req)
        assert resp.is_success()
        assert not d.exists()

    def test_delete_path_traversal(self, workspace):
        tool = DeleteTool(workspace=workspace)
        req = make_request("deletetool", {"path": "../../etc/passwd", "confirm": True})
        resp = tool.handle(req)
        assert not resp.is_success()
