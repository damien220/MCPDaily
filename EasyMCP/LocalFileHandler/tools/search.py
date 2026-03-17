"""SearchTool — search workspace files by name, type, date, and size."""

from __future__ import annotations

import re
from datetime import datetime, timezone
from pathlib import Path

from core.models import MCPRequest, MCPResponse
from core.tool_base import BaseTool


class SearchTool(BaseTool):
    """Search files in the workspace by name pattern, type, date range, and size."""

    def __init__(self, workspace: Path, **kwargs):
        super().__init__(**kwargs)
        self.workspace = workspace

    def _safe_path(self, user_path: str) -> Path | None:
        resolved = (self.workspace / user_path).resolve()
        if not str(resolved).startswith(str(self.workspace.resolve())):
            return None
        return resolved

    def _parse_date(self, date_str: str) -> datetime | None:
        """Parse an ISO date string (YYYY-MM-DD or full ISO)."""
        for fmt in ("%Y-%m-%d", "%Y-%m-%dT%H:%M:%S"):
            try:
                dt = datetime.strptime(date_str, fmt)
                return dt.replace(tzinfo=timezone.utc)
            except ValueError:
                continue
        return None

    def handle(self, request: MCPRequest) -> MCPResponse:
        query: str | None = request.payload.get("query")
        file_type: str | None = request.payload.get("type")      # extension filter
        date_from: str | None = request.payload.get("date_from")  # ISO date
        date_to: str | None = request.payload.get("date_to")      # ISO date
        min_size: int | None = request.payload.get("min_size")    # bytes
        max_size: int | None = request.payload.get("max_size")    # bytes
        search_root: str = request.payload.get("path", ".")
        use_regex: bool = request.payload.get("regex", False)
        limit: int = min(int(request.payload.get("limit", 100)), 500)

        root = self._safe_path(search_root)
        if root is None:
            return MCPResponse.failure(request, "Path is outside the workspace.")
        if not root.exists():
            return MCPResponse.failure(request, f"Search root does not exist: {search_root}")
        if not root.is_dir():
            return MCPResponse.failure(request, f"Search root is not a directory: {search_root}")

        # Compile name pattern
        name_pattern: re.Pattern | None = None
        if query:
            try:
                if use_regex:
                    name_pattern = re.compile(query, re.IGNORECASE)
                else:
                    # Treat query as a glob-style substring match
                    escaped = re.escape(query)
                    name_pattern = re.compile(escaped, re.IGNORECASE)
            except re.error as e:
                return MCPResponse.failure(request, f"Invalid regex pattern: {e}")

        # Normalize extension filter
        ext_filter: str | None = None
        if file_type:
            ext_filter = file_type if file_type.startswith(".") else f".{file_type}"
            ext_filter = ext_filter.lower()

        # Parse date filters
        dt_from = self._parse_date(date_from) if date_from else None
        dt_to = self._parse_date(date_to) if date_to else None

        try:
            matches = []
            for item in sorted(root.rglob("*")):
                if not item.is_file():
                    continue

                # Skip hidden system dirs (.trash, .history)
                parts = item.relative_to(self.workspace).parts
                if any(p.startswith(".") for p in parts[:-1]):
                    continue

                # Extension filter
                if ext_filter and item.suffix.lower() != ext_filter:
                    continue

                # Name pattern filter
                if name_pattern and not name_pattern.search(item.name):
                    continue

                stat = item.stat()

                # Date filters
                mtime = datetime.fromtimestamp(stat.st_mtime, tz=timezone.utc)
                if dt_from and mtime < dt_from:
                    continue
                if dt_to and mtime > dt_to:
                    continue

                # Size filters
                if min_size is not None and stat.st_size < min_size:
                    continue
                if max_size is not None and stat.st_size > max_size:
                    continue

                matches.append({
                    "name": item.name,
                    "path": str(item.relative_to(self.workspace)),
                    "extension": item.suffix,
                    "size": stat.st_size,
                    "modified": mtime.isoformat(),
                })

                if len(matches) >= limit:
                    break

            return MCPResponse.success(
                request,
                {
                    "query": query,
                    "search_root": search_root,
                    "count": len(matches),
                    "results": matches,
                },
            )
        except Exception as e:
            return MCPResponse.failure(request, f"Search failed: {e}")
