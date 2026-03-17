"""UndoTool — reverse the last N undoable file operations."""

from __future__ import annotations

import shutil
from pathlib import Path

from core.models import MCPRequest, MCPResponse
from core.tool_base import BaseTool

from ..history import Operation, OperationLog


class UndoTool(BaseTool):
    """Reverse the most recent undoable operations recorded in the history log."""

    def __init__(self, workspace: Path, operation_log: OperationLog, **kwargs):
        super().__init__(**kwargs)
        self.workspace = workspace
        self.operation_log = operation_log

    def handle(self, request: MCPRequest) -> MCPResponse:
        steps: int = max(1, int(request.payload.get("steps", 1)))
        preview: bool = request.payload.get("preview", False)

        try:
            stack = self.operation_log.undoable_stack(limit=steps)
            if not stack:
                return MCPResponse.failure(
                    request, "No undoable operations in history."
                )

            results = []
            for op in stack:
                entry = {
                    "operation_id": op.id,
                    "tool": op.tool,
                    "timestamp": op.timestamp,
                    "undo_data": op.undo_data,
                }
                if not preview:
                    error = self._execute_undo(op)
                    if error:
                        entry["status"] = "failed"
                        entry["error"] = error
                    else:
                        self.operation_log.mark_undone(op.id)
                        entry["status"] = "undone"
                else:
                    entry["status"] = "preview"
                results.append(entry)

            return MCPResponse.success(
                request,
                {
                    "preview": preview,
                    "undone_count": sum(1 for r in results if r["status"] == "undone"),
                    "results": results,
                },
            )
        except Exception as e:
            return MCPResponse.failure(request, f"Undo failed: {e}")

    def _execute_undo(self, op: Operation) -> str | None:
        """Execute the reverse action for an operation.

        Returns None on success, or an error string on failure.
        """
        action = op.undo_data.get("action")
        try:
            if action == "delete_file":
                path = Path(op.undo_data["path"])
                if path.exists():
                    path.unlink()
                    return None
                return f"File no longer exists: {path}"

            elif action == "delete_dir":
                path = Path(op.undo_data["path"])
                if path.exists() and path.is_dir():
                    shutil.rmtree(path)
                    return None
                return f"Directory no longer exists: {path}"

            elif action == "rename":
                from_path = Path(op.undo_data["from_path"])
                to_path = Path(op.undo_data["to_path"])
                if not from_path.exists():
                    return f"Source no longer exists: {from_path}"
                if to_path.exists():
                    return f"Target already exists: {to_path}"
                from_path.rename(to_path)
                return None

            elif action == "move":
                from_path = Path(op.undo_data["from_path"])
                to_dir = Path(op.undo_data["to_dir"])
                if not from_path.exists():
                    return f"File no longer exists: {from_path}"
                to_dir.mkdir(parents=True, exist_ok=True)
                dest = to_dir / from_path.name
                if dest.exists():
                    return f"Target already exists: {dest}"
                shutil.move(str(from_path), str(dest))
                return None

            elif action == "restore_from_trash":
                trash_path = Path(op.undo_data["trash_path"])
                original_path = Path(op.undo_data["original_path"])
                if not trash_path.exists():
                    return f"Trash item no longer exists: {trash_path}"
                if original_path.exists():
                    return f"Original location already occupied: {original_path}"
                original_path.parent.mkdir(parents=True, exist_ok=True)
                shutil.move(str(trash_path), str(original_path))
                return None

            elif action == "undo_organize":
                ws = Path(op.undo_data.get("workspace", str(self.workspace)))
                moves = op.undo_data.get("moves", [])
                errors = []
                for m in moves:
                    src = ws / m["from_path"]
                    dst = ws / m["to_path"]
                    if not src.exists():
                        errors.append(f"Missing: {src}")
                        continue
                    dst.parent.mkdir(parents=True, exist_ok=True)
                    shutil.move(str(src), str(dst))
                return "; ".join(errors) if errors else None

            elif action == "none":
                return "This operation was a permanent delete and cannot be undone."

            else:
                return f"Unknown undo action: {action}"

        except Exception as e:
            return str(e)
