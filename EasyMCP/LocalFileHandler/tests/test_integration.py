"""Integration tests — full CLI flow with all tools working together."""

import json
import subprocess
import sys
import tempfile
from pathlib import Path

import pytest


PYTHON = str(Path(__file__).resolve().parent.parent / ".venv" / "bin" / "python")
PROJECT_ROOT = str(Path(__file__).resolve().parent.parent.parent)


def run_cli(*requests: dict) -> list[dict]:
    """Send JSON requests to the CLI server and return parsed responses."""
    input_lines = "\n".join(json.dumps(r) for r in requests)
    result = subprocess.run(
        [PYTHON, "-m", "LocalFileHandler"],
        input=input_lines,
        capture_output=True,
        text=True,
        cwd=PROJECT_ROOT,
        timeout=10,
    )
    # Parse response lines (skip stderr)
    responses = []
    for line in result.stdout.strip().splitlines():
        line = line.strip()
        if line.startswith("{"):
            responses.append(json.loads(line))
    return responses


class TestFullCLIFlow:
    """Test a complete workflow: create → list → rename → move → delete."""

    def test_create_and_list(self):
        responses = run_cli(
            {"id": "1", "tool": "createfiletool", "payload": {"name": "integration test", "type": "md", "content": "# Test"}},
            {"id": "2", "tool": "listcontentstool", "payload": {"path": ".", "recursive": True}},
        )
        assert len(responses) == 2
        assert responses[0]["status"] == "success"
        assert "integration-test" in responses[0]["result"]["path"]
        assert responses[1]["status"] == "success"
        assert responses[1]["result"]["count"] > 0

    def test_create_dir_and_list(self):
        responses = run_cli(
            {"id": "1", "tool": "createdirtool", "payload": {"name": "Test Project"}},
            {"id": "2", "tool": "listcontentstool", "payload": {"path": "projects", "recursive": False}},
        )
        assert responses[0]["status"] == "success"
        assert "test-project" in responses[0]["result"]["path"]
        assert responses[1]["status"] == "success"

    def test_error_handling_delete_nonexistent(self):
        responses = run_cli(
            {"id": "1", "tool": "deletetool", "payload": {"path": "nonexistent", "confirm": True}},
        )
        assert len(responses) == 1
        assert responses[0]["status"] == "error"

    def test_error_handling_missing_name(self):
        responses = run_cli(
            {"id": "1", "tool": "createfiletool", "payload": {}},
        )
        assert len(responses) == 1
        assert responses[0]["status"] == "error"

    def test_error_handling_unknown_tool(self):
        """Framework raises ToolNotRegisteredError for unknown tools (crashes CLI)."""
        result = subprocess.run(
            [PYTHON, "-m", "LocalFileHandler"],
            input='{"id":"1","tool":"nonexistenttool","payload":{}}',
            capture_output=True,
            text=True,
            cwd=PROJECT_ROOT,
            timeout=10,
        )
        # The framework's CLIServer does not handle unknown tools gracefully —
        # it raises KeyError, so stderr should contain the error
        assert result.returncode != 0

    def test_delete_requires_confirm(self):
        responses = run_cli(
            {"id": "1", "tool": "createfiletool", "payload": {"name": "temp", "type": "txt"}},
            {"id": "2", "tool": "deletetool", "payload": {"path": "documents/temp.txt"}},
        )
        # Create succeeds, delete fails (no confirm)
        assert responses[0]["status"] == "success"
        assert responses[1]["status"] == "error"
        assert "confirm" in responses[1]["error"].lower()
