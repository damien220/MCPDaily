"""MCP tool for marking a task as completed."""

from __future__ import annotations

from core.models import MCPRequest, MCPResponse
from core.tool_base import BaseTool

from ..storage import TaskStorage


class CompleteTaskTool(BaseTool):
    """Mark an existing task as completed by its ID."""

    def __init__(self, storage: TaskStorage) -> None:
        super().__init__(name="completetask")
        self.storage = storage

    def handle(self, request: MCPRequest) -> MCPResponse:
        task_id = request.payload.get("task_id")
        if not task_id:
            return MCPResponse.failure(request, "Payload must include 'task_id'.")

        task = self.storage.complete_task(str(task_id))
        if task is None:
            return MCPResponse.failure(request, f"Task '{task_id}' not found.")

        return MCPResponse.success(request, task)
