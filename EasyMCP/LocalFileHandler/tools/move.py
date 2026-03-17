"""MoveTool — move files/directories with auto-categorization."""

from __future__ import annotations

import shutil
from pathlib import Path

from core.models import MCPRequest, MCPResponse
from core.tool_base import BaseTool

from ..history import Operation, OperationLog
from ..naming import NameFormatter


class MoveTool(BaseTool):
    """Move a file or directory to a new location within the workspace."""

    def __init__(
        self,
        workspace: Path,
        formatter: NameFormatter,
        operation_log: OperationLog | None = None,
        **kwargs,
    ):
        super().__init__(**kwargs)
        self.workspace = workspace
        self.formatter = formatter
        self.operation_log = operation_log

    def _safe_path(self, user_path: str) -> Path | None:
        resolved = (self.workspace / user_path).resolve()
        if not str(resolved).startswith(str(self.workspace.resolve())):
            return None
        return resolved

    def handle(self, request: MCPRequest) -> MCPResponse:
        source_str = request.payload.get("source")
        dest_str = request.payload.get("destination")

        if not source_str:
            return MCPResponse.failure(
                request, "Payload must include a 'source' field."
            )
        if not dest_str:
            return MCPResponse.failure(
                request, "Payload must include a 'destination' field."
            )

        source = self._safe_path(source_str)
        destination = self._safe_path(dest_str)

        if source is None or destination is None:
            return MCPResponse.failure(request, "Path is outside the workspace.")
        if not source.exists():
            return MCPResponse.failure(
                request, f"Source does not exist: {source_str}"
            )

        try:
            if destination.is_dir() or dest_str.endswith("/"):
                destination.mkdir(parents=True, exist_ok=True)
                new_path = destination / source.name
            else:
                destination.parent.mkdir(parents=True, exist_ok=True)
                new_path = destination

            if new_path.exists():
                return MCPResponse.failure(
                    request,
                    f"Target already exists: {new_path.relative_to(self.workspace)}",
                )

            shutil.move(str(source), str(new_path))

            result = {
                "old_path": str(source.relative_to(self.workspace)),
                "new_path": str(new_path.relative_to(self.workspace)),
            }
            response = MCPResponse.success(request, result)

            if self.operation_log:
                self.operation_log.record(
                    Operation(
                        tool=self.name,
                        status="success",
                        payload=dict(request.payload),
                        result=result,
                        undoable=True,
                        undo_data={
                            "action": "move",
                            "from_path": str(new_path),
                            "to_dir": str(source.parent),
                        },
                        request_id=request.id,
                    )
                )
            return response
        except Exception as e:
            return MCPResponse.failure(request, f"Failed to move: {e}")
