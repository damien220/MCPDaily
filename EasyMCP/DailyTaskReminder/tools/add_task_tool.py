"""MCP tool for adding a new task."""

from __future__ import annotations

from core.models import MCPRequest, MCPResponse
from core.tool_base import BaseTool

from ..storage import TaskStorage


class AddTaskTool(BaseTool):
    """Add a new task with title, optional description, due date, and reminder."""

    def __init__(self, storage: TaskStorage) -> None:
        super().__init__(name="addtask")
        self.storage = storage

    def handle(self, request: MCPRequest) -> MCPResponse:
        title = request.payload.get("title")
        if not title or not str(title).strip():
            return MCPResponse.failure(request, "Payload must include a non-empty 'title'.")

        task = self.storage.add_task(
            title=str(title).strip(),
            description=str(request.payload.get("description", "")).strip(),
            due_at=request.payload.get("due_at"),
            remind_at=request.payload.get("remind_at"),
        )
        return MCPResponse.success(request, task)
