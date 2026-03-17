"""Data model for a recorded file operation."""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any


@dataclass
class Operation:
    """Represents a single file-system operation performed by a tool.

    Attributes:
        id: Unique identifier (UUID4).
        timestamp: ISO 8601 UTC timestamp of when the operation ran.
        tool: Tool name that performed the operation (e.g. "createfiletool").
        status: "success" or "error".
        payload: The original MCP request payload.
        result: The successful result dict (empty on error).
        undoable: Whether this operation can be reversed by UndoTool.
        undo_data: Data required to reverse the operation.
            Keys are action-specific; see each tool for details.
        undone: True if this operation has already been undone.
        request_id: The MCP request ID for tracing.
    """

    tool: str
    status: str
    payload: dict[str, Any]
    result: dict[str, Any]
    undoable: bool
    undo_data: dict[str, Any]
    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    timestamp: str = field(
        default_factory=lambda: datetime.now(tz=timezone.utc).isoformat()
    )
    undone: bool = False
    request_id: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "timestamp": self.timestamp,
            "tool": self.tool,
            "status": self.status,
            "payload": self.payload,
            "result": self.result,
            "undoable": self.undoable,
            "undo_data": self.undo_data,
            "undone": self.undone,
            "request_id": self.request_id,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> Operation:
        return cls(
            id=data["id"],
            timestamp=data["timestamp"],
            tool=data["tool"],
            status=data["status"],
            payload=data.get("payload", {}),
            result=data.get("result", {}),
            undoable=data.get("undoable", False),
            undo_data=data.get("undo_data", {}),
            undone=data.get("undone", False),
            request_id=data.get("request_id", ""),
        )
