"""RenameTool — rename files/directories with naming rules enforcement."""

from __future__ import annotations

from pathlib import Path

from core.models import MCPRequest, MCPResponse
from core.tool_base import BaseTool

from ..history import Operation, OperationLog
from ..naming import NameFormatter


class RenameTool(BaseTool):
    """Rename a file or directory with naming rules applied to the new name."""

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
        path_str = request.payload.get("path")
        new_name = request.payload.get("new_name")

        if not path_str:
            return MCPResponse.failure(request, "Payload must include a 'path' field.")
        if not new_name:
            return MCPResponse.failure(
                request, "Payload must include a 'new_name' field."
            )

        source = self._safe_path(path_str)
        if source is None:
            return MCPResponse.failure(request, "Path is outside the workspace.")
        if not source.exists():
            return MCPResponse.failure(request, f"Path does not exist: {path_str}")

        try:
            if source.is_dir():
                stem, _, rules_applied = self.formatter.format_rename(new_name)
                new_path = source.parent / stem
            else:
                extension = source.suffix
                stem, ext, rules_applied = self.formatter.format_rename(
                    new_name, extension
                )
                new_path = source.parent / f"{stem}{ext}"

            if new_path.exists() and new_path != source:
                return MCPResponse.failure(
                    request,
                    f"Target already exists: {new_path.relative_to(self.workspace)}",
                )

            source.rename(new_path)

            result = {
                "old_path": str(source.relative_to(self.workspace)),
                "new_path": str(new_path.relative_to(self.workspace)),
                "rules_applied": rules_applied,
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
                            "action": "rename",
                            "from_path": str(new_path),
                            "to_path": str(source),
                        },
                        request_id=request.id,
                    )
                )
            return response
        except Exception as e:
            return MCPResponse.failure(request, f"Failed to rename: {e}")
