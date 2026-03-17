"""Integration tests for HTTP server mode — tests POST /invoke via requests."""

from __future__ import annotations

import json
import subprocess
import time
from pathlib import Path

import pytest
import requests


PYTHON = str(Path(__file__).resolve().parent.parent / ".venv" / "bin" / "python")
PROJECT_ROOT = str(Path(__file__).resolve().parent.parent.parent)
HTTP_PORT = 18080  # separate port to avoid conflicts
BASE_URL = f"http://127.0.0.1:{HTTP_PORT}/invoke"


def invoke(tool: str, payload: dict, req_id: str = "t1") -> dict:
    resp = requests.post(
        BASE_URL,
        json={"id": req_id, "tool": tool, "payload": payload},
        timeout=5,
    )
    resp.raise_for_status()
    return resp.json()


@pytest.fixture(scope="module")
def http_server():
    """Start the HTTP server once for all tests in this module."""
    proc = subprocess.Popen(
        [PYTHON, "-m", "LocalFileHandler", "--mode", "http", "--port", str(HTTP_PORT)],
        cwd=PROJECT_ROOT,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    # Wait for server to be ready
    for _ in range(20):
        try:
            requests.post(BASE_URL, json={"id": "0", "tool": "listcontentstool", "payload": {"path": "."}}, timeout=1)
            break
        except Exception:
            time.sleep(0.3)
    yield proc
    proc.terminate()
    proc.wait(timeout=5)


class TestHTTPServer:
    def test_list_contents(self, http_server):
        result = invoke("listcontentstool", {"path": "."})
        assert result["status"] == "success"
        assert "entries" in result["result"]

    def test_create_file(self, http_server):
        result = invoke("createfiletool", {"name": "http integration", "type": "txt", "content": "hello"})
        assert result["status"] == "success"
        assert "http-integration" in result["result"]["path"]

    def test_search(self, http_server):
        invoke("createfiletool", {"name": "searchable doc", "type": "md", "content": ""})
        result = invoke("searchtool", {"query": "searchable"})
        assert result["status"] == "success"

    def test_config_get(self, http_server):
        result = invoke("configtool", {"action": "get"})
        assert result["status"] == "success"
        assert "naming" in result["result"]

    def test_history(self, http_server):
        result = invoke("historytool", {"limit": 5})
        assert result["status"] == "success"
        assert "operations" in result["result"]

    def test_info(self, http_server):
        invoke("createfiletool", {"name": "info target", "type": "txt", "content": "data"})
        # search to find the actual path
        search = invoke("searchtool", {"query": "info-target"})
        if search["result"]["count"] > 0:
            path = search["result"]["results"][0]["path"]
            result = invoke("infotool", {"path": path})
            assert result["status"] == "success"
            assert result["result"]["type"] == "file"

    def test_error_missing_name(self, http_server):
        result = invoke("createfiletool", {})
        assert result["status"] == "error"

    def test_multiple_requests_in_sequence(self, http_server):
        results = [
            invoke("configtool", {"action": "get"}, req_id=str(i))
            for i in range(5)
        ]
        assert all(r["status"] == "success" for r in results)
