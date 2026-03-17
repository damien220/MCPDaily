"""ListContentsTool — list directory contents with metadata."""

import os
from datetime import datetime, timezone
from pathlib import Path

from core.models import MCPRequest, MCPResponse
from core.tool_base import BaseTool


class ListContentsTool(BaseTool):
    """List the contents of a directory with file metadata."""

    def __init__(self, workspace: Path, **kwargs):
        super().__init__(**kwargs)
        self.workspace = workspace

    def _safe_path(self, user_path: str) -> Path | None:
        """Resolve a user-provided path and ensure it stays within the workspace."""
        resolved = (self.workspace / user_path).resolve()
        if not str(resolved).startswith(str(self.workspace.resolve())):
            return None
        return resolved

    def handle(self, request: MCPRequest) -> MCPResponse:
        rel_path = request.payload.get("path", ".")
        recursive = request.payload.get("recursive", False)

        target = self._safe_path(rel_path)
        if target is None:
            return MCPResponse.failure(request, "Path is outside the workspace.")
        if not target.exists():
            return MCPResponse.failure(request, f"Path does not exist: {rel_path}")
        if not target.is_dir():
            return MCPResponse.failure(request, f"Path is not a directory: {rel_path}")

        try:
            entries = []
            iterator = target.rglob("*") if recursive else target.iterdir()
            for item in sorted(iterator):
                stat = item.stat()
                entry = {
                    "name": item.name,
                    "path": str(item.relative_to(self.workspace)),
                    "type": "directory" if item.is_dir() else "file",
                    "size": stat.st_size if item.is_file() else None,
                    "modified": datetime.fromtimestamp(
                        stat.st_mtime, tz=timezone.utc
                    ).isoformat(),
                }
                if item.is_file():
                    entry["extension"] = item.suffix
                entries.append(entry)

            return MCPResponse.success(
                request,
                {
                    "path": str(target.relative_to(self.workspace)),
                    "count": len(entries),
                    "entries": entries,
                },
            )
        except Exception as e:
            return MCPResponse.failure(request, f"Failed to list contents: {e}")
