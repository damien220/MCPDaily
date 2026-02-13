"""MCP tool for checking due reminders."""

from __future__ import annotations

from core.models import MCPRequest, MCPResponse
from core.tool_base import BaseTool

from ..storage import TaskStorage


class CheckRemindersTool(BaseTool):
    """Check for tasks whose reminders are due and mark them as notified."""

    def __init__(self, storage: TaskStorage) -> None:
        super().__init__(name="checkreminders")
        self.storage = storage

    def handle(self, request: MCPRequest) -> MCPResponse:
        due_tasks = self.storage.get_due_reminders()
        return MCPResponse.success(request, {"count": len(due_tasks), "tasks": due_tasks})
