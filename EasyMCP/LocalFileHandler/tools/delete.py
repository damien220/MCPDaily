"""DeleteTool — safe delete with trash support."""

from __future__ import annotations

import shutil
from datetime import datetime
from pathlib import Path

from core.models import MCPRequest, MCPResponse
from core.tool_base import BaseTool

from ..history import Operation, OperationLog


class DeleteTool(BaseTool):
    """Delete a file or directory with optional trash (soft-delete) support."""

    def __init__(
        self,
        workspace: Path,
        trash_enabled: bool = True,
        trash_dir: str = ".trash",
        operation_log: OperationLog | None = None,
        **kwargs,
    ):
        super().__init__(**kwargs)
        self.workspace = workspace
        self.trash_enabled = trash_enabled
        self.trash_dir = trash_dir
        self.operation_log = operation_log

    def _safe_path(self, user_path: str) -> Path | None:
        resolved = (self.workspace / user_path).resolve()
        if not str(resolved).startswith(str(self.workspace.resolve())):
            return None
        return resolved

    def handle(self, request: MCPRequest) -> MCPResponse:
        path_str = request.payload.get("path")
        confirm = request.payload.get("confirm", False)

        if not path_str:
            return MCPResponse.failure(request, "Payload must include a 'path' field.")
        if not confirm:
            return MCPResponse.failure(
                request,
                "Delete requires 'confirm': true in the payload for safety.",
            )

        target = self._safe_path(path_str)
        if target is None:
            return MCPResponse.failure(request, "Path is outside the workspace.")
        if not target.exists():
            return MCPResponse.failure(request, f"Path does not exist: {path_str}")

        trash_path = self.workspace / self.trash_dir
        if target.resolve() == trash_path.resolve():
            return MCPResponse.failure(request, "Cannot delete the trash directory.")

        try:
            moved_to_trash = False
            trash_dest: Path | None = None

            if self.trash_enabled:
                trash_path.mkdir(parents=True, exist_ok=True)
                timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                trash_name = f"{timestamp}_{target.name}"
                trash_dest = trash_path / trash_name
                shutil.move(str(target), str(trash_dest))
                moved_to_trash = True
            else:
                if target.is_dir():
                    shutil.rmtree(target)
                else:
                    target.unlink()

            result = {
                "deleted": str(target.relative_to(self.workspace)),
                "moved_to_trash": moved_to_trash,
            }
            response = MCPResponse.success(request, result)

            if self.operation_log:
                undo_data: dict
                if moved_to_trash and trash_dest is not None:
                    undo_data = {
                        "action": "restore_from_trash",
                        "trash_path": str(trash_dest),
                        "original_path": str(target),
                    }
                else:
                    undo_data = {"action": "none"}  # permanent delete cannot be undone
                self.operation_log.record(
                    Operation(
                        tool=self.name,
                        status="success",
                        payload=dict(request.payload),
                        result=result,
                        undoable=moved_to_trash,
                        undo_data=undo_data,
                        request_id=request.id,
                    )
                )
            return response
        except Exception as e:
            return MCPResponse.failure(request, f"Failed to delete: {e}")
