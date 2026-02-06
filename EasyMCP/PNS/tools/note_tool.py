"""
NoteTool - CRUD operations for notes.

Actions:
- create: Create a new note (requires: title, content; optional: tags)
- read: Read a note by ID (requires: note_id)
- update: Update an existing note (requires: note_id; optional: title, content, tags)
- delete: Delete a note by ID (requires: note_id)
- list: List all notes (optional: tag, limit, offset)
"""

from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from slugify import slugify

from storage.file_storage import FileStorage, Note
from core.tool_base import BaseTool
from core.models import MCPResponse

class NoteTool(BaseTool):
    """Tool for managing notes with CRUD operations."""

    name = "notetool"
    description = "Create, read, update, delete, and list notes"

    def __init__(self, storage_path: Path):
        """
        Initialize NoteTool.

        Args:
            storage_path: Path to the notes storage directory.
        """
        super().__init__()
        self.storage = FileStorage(storage_path)

    def _make_response(self, request: Any, data: dict[str, Any], success: bool = True) -> MCPResponse:
        """Create an MCPResponse from the request and data."""
        request_id = request.id if hasattr(request, 'id') else "unknown"
        status = "success" if success else "error"
        return MCPResponse(id=request_id, status=status, result=data)

    def handle(self, request: Any) -> MCPResponse:
        """
        Handle a note action.

        Args:
            request: MCPRequest object containing payload with 'action' and action-specific fields.

        Returns:
            MCPResponse object with result data.
        """
        # Extract payload from MCPRequest object
        payload = request.payload if hasattr(request, 'payload') else request

        action = payload.get("action", "").lower()

        actions = {
            "create": self._create,
            "read": self._read,
            "update": self._update,
            "delete": self._delete,
            "list": self._list,
        }

        if action not in actions:
            return self._make_response(request, {
                "success": False,
                "error": f"Unknown action: {action}. Valid actions: {', '.join(actions.keys())}",
            }, success=False)

        try:
            result = actions[action](payload)
            is_success = result.get("success", True)
            return self._make_response(request, result, success=is_success)
        except Exception as e:
            return self._make_response(request, {
                "success": False,
                "error": str(e),
            }, success=False)

    def _generate_note_id(self, title: str) -> str:
        """
        Generate a unique note ID from title and current date.

        Format: {date}-{slug} (e.g., 2025-01-29-my-note-title)
        """
        date_prefix = datetime.now(timezone.utc).strftime("%Y-%m-%d")
        slug = slugify(title, max_length=50, word_boundary=True)

        note_id = f"{date_prefix}-{slug}"

        # Ensure uniqueness by appending counter if necessary
        if self.storage.exists(note_id):
            counter = 1
            while self.storage.exists(f"{note_id}-{counter}"):
                counter += 1
            note_id = f"{note_id}-{counter}"

        return note_id

    def _create(self, payload: dict[str, Any]) -> dict[str, Any]:
        """Create a new note."""
        # Validate required fields
        title = payload.get("title")
        content = payload.get("content")

        if not title:
            return {"success": False, "error": "Missing required field: title"}
        if not content:
            return {"success": False, "error": "Missing required field: content"}

        # Get optional fields
        tags = payload.get("tags", [])
        if isinstance(tags, str):
            tags = [t.strip() for t in tags.split(",") if t.strip()]

        # Generate note ID
        note_id = self._generate_note_id(title)

        # Create note
        note = Note(
            id=note_id,
            title=title,
            content=content,
            tags=tags,
        )

        # Save note
        saved_note = self.storage.save(note)

        return {
            "success": True,
            "message": "Note created successfully",
            "note": saved_note.to_dict(),
        }

    def _read(self, payload: dict[str, Any]) -> dict[str, Any]:
        """Read a note by ID."""
        note_id = payload.get("note_id")

        if not note_id:
            return {"success": False, "error": "Missing required field: note_id"}

        note = self.storage.get(note_id)

        if not note:
            return {"success": False, "error": f"Note not found: {note_id}"}

        return {
            "success": True,
            "note": note.to_dict(),
        }

    def _update(self, payload: dict[str, Any]) -> dict[str, Any]:
        """Update an existing note."""
        note_id = payload.get("note_id")

        if not note_id:
            return {"success": False, "error": "Missing required field: note_id"}

        # Get existing note
        note = self.storage.get(note_id)

        if not note:
            return {"success": False, "error": f"Note not found: {note_id}"}

        # Update fields if provided
        if "title" in payload:
            note.title = payload["title"]
        if "content" in payload:
            note.content = payload["content"]
        if "tags" in payload:
            tags = payload["tags"]
            if isinstance(tags, str):
                tags = [t.strip() for t in tags.split(",") if t.strip()]
            note.tags = tags

        # Save updated note
        saved_note = self.storage.save(note)

        return {
            "success": True,
            "message": "Note updated successfully",
            "note": saved_note.to_dict(),
        }

    def _delete(self, payload: dict[str, Any]) -> dict[str, Any]:
        """Delete a note by ID."""
        note_id = payload.get("note_id")

        if not note_id:
            return {"success": False, "error": "Missing required field: note_id"}

        deleted = self.storage.delete(note_id)

        if not deleted:
            return {"success": False, "error": f"Note not found: {note_id}"}

        return {
            "success": True,
            "message": f"Note deleted successfully: {note_id}",
        }

    def _list(self, payload: dict[str, Any]) -> dict[str, Any]:
        """List all notes with optional filtering."""
        tag = payload.get("tag")
        limit = payload.get("limit", 100)
        offset = payload.get("offset", 0)

        # Validate limit and offset
        try:
            limit = int(limit)
            offset = int(offset)
        except (ValueError, TypeError):
            return {"success": False, "error": "limit and offset must be integers"}

        if limit < 1:
            limit = 100
        if offset < 0:
            offset = 0

        notes = self.storage.list_all(tag=tag, limit=limit, offset=offset)
        total = self.storage.count(tag=tag)

        return {
            "success": True,
            "notes": [note.to_dict() for note in notes],
            "total": total,
            "limit": limit,
            "offset": offset,
            "has_more": offset + len(notes) < total,
        }
