"""HistoryTool — query the operation history log."""

from __future__ import annotations

from pathlib import Path

from core.models import MCPRequest, MCPResponse
from core.tool_base import BaseTool

from ..history import OperationLog


class HistoryTool(BaseTool):
    """Query the history of file operations performed by the server."""

    def __init__(self, operation_log: OperationLog, **kwargs):
        super().__init__(**kwargs)
        self.operation_log = operation_log

    def handle(self, request: MCPRequest) -> MCPResponse:
        limit: int = min(int(request.payload.get("limit", 20)), 200)
        tool_filter: str | None = request.payload.get("tool")
        status_filter: str | None = request.payload.get("status")
        op_id: str | None = request.payload.get("id")

        try:
            # Single operation lookup
            if op_id:
                op = self.operation_log.get_by_id(op_id)
                if op is None:
                    return MCPResponse.failure(
                        request, f"Operation not found: {op_id}"
                    )
                return MCPResponse.success(request, {"operation": op.to_dict()})

            ops = self.operation_log.get_recent(
                limit=limit,
                tool_filter=tool_filter,
                status_filter=status_filter,
            )

            return MCPResponse.success(
                request,
                {
                    "count": len(ops),
                    "limit": limit,
                    "operations": [o.to_dict() for o in ops],
                },
            )
        except Exception as e:
            return MCPResponse.failure(request, f"Failed to query history: {e}")
