"""CreateDirTool — create directories with AI-driven naming rules."""

from __future__ import annotations

from pathlib import Path

from core.models import MCPRequest, MCPResponse
from core.tool_base import BaseTool

from ..history import Operation, OperationLog
from ..naming import NameFormatter


class CreateDirTool(BaseTool):
    """Create a directory with intelligent naming rules applied automatically."""

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

    def handle(self, request: MCPRequest) -> MCPResponse:
        name = request.payload.get("name")
        if not name:
            return MCPResponse.failure(request, "Payload must include a 'name' field.")

        try:
            full_path, rules_applied = self.formatter.format_dirname(name)
            full_path.mkdir(parents=True, exist_ok=True)

            result = {
                "path": str(full_path.relative_to(self.workspace.parent)) + "/",
                "absolute_path": str(full_path),
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
                            "action": "delete_dir",
                            "path": str(full_path),
                        },
                        request_id=request.id,
                    )
                )
            return response
        except Exception as e:
            return MCPResponse.failure(request, f"Failed to create directory: {e}")
