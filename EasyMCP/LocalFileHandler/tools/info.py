"""InfoTool — return detailed metadata for a file or directory."""

from __future__ import annotations

import hashlib
import mimetypes
import os
import stat
from datetime import datetime, timezone
from pathlib import Path

from core.models import MCPRequest, MCPResponse
from core.tool_base import BaseTool


class InfoTool(BaseTool):
    """Return detailed metadata for a file or directory in the workspace."""

    def __init__(self, workspace: Path, **kwargs):
        super().__init__(**kwargs)
        self.workspace = workspace

    def _safe_path(self, user_path: str) -> Path | None:
        resolved = (self.workspace / user_path).resolve()
        if not str(resolved).startswith(str(self.workspace.resolve())):
            return None
        return resolved

    @staticmethod
    def _md5(path: Path, chunk_size: int = 65536) -> str:
        h = hashlib.md5()
        with path.open("rb") as fh:
            while chunk := fh.read(chunk_size):
                h.update(chunk)
        return h.hexdigest()

    @staticmethod
    def _permissions_str(mode: int) -> str:
        """Convert a stat mode integer to a human-readable string (e.g. 'rw-r--r--')."""
        result = []
        for who in ("USR", "GRP", "OTH"):
            result.append("r" if mode & getattr(stat, f"S_IR{who}") else "-")
            result.append("w" if mode & getattr(stat, f"S_IW{who}") else "-")
            result.append("x" if mode & getattr(stat, f"S_IX{who}") else "-")
        return "".join(result)

    def handle(self, request: MCPRequest) -> MCPResponse:
        path_str = request.payload.get("path")
        include_hash: bool = request.payload.get("hash", True)

        if not path_str:
            return MCPResponse.failure(request, "Payload must include a 'path' field.")

        target = self._safe_path(path_str)
        if target is None:
            return MCPResponse.failure(request, "Path is outside the workspace.")
        if not target.exists():
            return MCPResponse.failure(request, f"Path does not exist: {path_str}")

        try:
            st = target.stat()
            mtime = datetime.fromtimestamp(st.st_mtime, tz=timezone.utc)
            ctime = datetime.fromtimestamp(st.st_ctime, tz=timezone.utc)

            info: dict = {
                "path": str(target.relative_to(self.workspace)),
                "name": target.name,
                "type": "directory" if target.is_dir() else "file",
                "permissions": self._permissions_str(st.st_mode),
                "modified": mtime.isoformat(),
                "created": ctime.isoformat(),
            }

            if target.is_file():
                mime_type, _ = mimetypes.guess_type(str(target))
                info.update({
                    "extension": target.suffix,
                    "size_bytes": st.st_size,
                    "size_human": self._human_size(st.st_size),
                    "mime_type": mime_type or "application/octet-stream",
                })
                if include_hash:
                    info["md5"] = self._md5(target)
            else:
                # Directory: count children
                children = list(target.iterdir())
                files = [c for c in children if c.is_file()]
                dirs = [c for c in children if c.is_dir()]
                info.update({
                    "children_count": len(children),
                    "file_count": len(files),
                    "dir_count": len(dirs),
                })

            return MCPResponse.success(request, info)
        except Exception as e:
            return MCPResponse.failure(request, f"Failed to get info: {e}")

    @staticmethod
    def _human_size(size_bytes: int) -> str:
        for unit in ("B", "KB", "MB", "GB", "TB"):
            if size_bytes < 1024:
                return f"{size_bytes:.1f} {unit}"
            size_bytes //= 1024
        return f"{size_bytes:.1f} PB"
