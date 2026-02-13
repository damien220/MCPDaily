"""MCP tool for listing tasks."""

from __future__ import annotations

from core.models import MCPRequest, MCPResponse
from core.tool_base import BaseTool

from ..storage import TaskStorage

VALID_FILTERS = {"all", "pending", "completed", "overdue"}


class ListTasksTool(BaseTool):
    """List tasks with an optional status filter."""

    def __init__(self, storage: TaskStorage) -> None:
        super().__init__(name="listtasks")
        self.storage = storage

    def handle(self, request: MCPRequest) -> MCPResponse:
        status_filter = request.payload.get("filter", "pending")
        if status_filter not in VALID_FILTERS:
            return MCPResponse.failure(
                request,
                f"Invalid filter '{status_filter}'. Must be one of: {', '.join(sorted(VALID_FILTERS))}.",
            )

        tasks = self.storage.list_tasks(status_filter)
        return MCPResponse.success(request, {"filter": status_filter, "count": len(tasks), "tasks": tasks})
