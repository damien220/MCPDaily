"""
File-based storage for notes using Markdown with YAML frontmatter.

Note format:
---
id: 2025-01-29-my-note
title: My Note
tags:
  - personal
created_at: 2025-01-29T10:30:00Z
updated_at: 2025-01-29T10:30:00Z
---

Note content here...
"""

import re
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

import yaml


@dataclass
class Note:
    """Represents a note with metadata and content."""

    id: str
    title: str
    content: str
    tags: list[str] = field(default_factory=list)
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))

    def to_markdown(self) -> str:
        """Convert note to markdown with YAML frontmatter."""
        frontmatter = {
            "id": self.id,
            "title": self.title,
            "tags": self.tags,
            "created_at": self.created_at.isoformat(),
            "updated_at": self.updated_at.isoformat(),
        }

        yaml_str = yaml.dump(frontmatter, default_flow_style=False, allow_unicode=True)
        return f"---\n{yaml_str}---\n\n{self.content}"

    def to_dict(self) -> dict:
        """Convert note to dictionary for JSON serialization."""
        return {
            "id": self.id,
            "title": self.title,
            "content": self.content,
            "tags": self.tags,
            "created_at": self.created_at.isoformat(),
            "updated_at": self.updated_at.isoformat(),
        }

    @classmethod
    def from_markdown(cls, markdown_content: str, file_id: str) -> "Note":
        """Parse markdown with YAML frontmatter into a Note object."""
        # Pattern to match YAML frontmatter
        frontmatter_pattern = re.compile(r"^---\s*\n(.*?)\n---\s*\n", re.DOTALL)
        match = frontmatter_pattern.match(markdown_content)

        if not match:
            # No frontmatter found, treat entire content as note body
            return cls(
                id=file_id,
                title=file_id,
                content=markdown_content.strip(),
            )

        yaml_content = match.group(1)
        body_content = markdown_content[match.end():].strip()

        try:
            metadata = yaml.safe_load(yaml_content) or {}
        except yaml.YAMLError:
            metadata = {}

        # Parse dates
        created_at = cls._parse_datetime(metadata.get("created_at"))
        updated_at = cls._parse_datetime(metadata.get("updated_at"))

        return cls(
            id=metadata.get("id", file_id),
            title=metadata.get("title", file_id),
            content=body_content,
            tags=metadata.get("tags", []) or [],
            created_at=created_at,
            updated_at=updated_at,
        )

    @staticmethod
    def _parse_datetime(value) -> datetime:
        """Parse datetime from various formats."""
        if value is None:
            return datetime.now(timezone.utc)
        if isinstance(value, datetime):
            return value if value.tzinfo else value.replace(tzinfo=timezone.utc)
        if isinstance(value, str):
            try:
                # Try ISO format
                dt = datetime.fromisoformat(value.replace("Z", "+00:00"))
                return dt if dt.tzinfo else dt.replace(tzinfo=timezone.utc)
            except ValueError:
                pass
        return datetime.now(timezone.utc)


class FileStorage:
    """File-based storage manager for notes."""

    def __init__(self, notes_directory: Path):
        """
        Initialize file storage.

        Args:
            notes_directory: Path to the directory where notes are stored.
        """
        self.notes_directory = Path(notes_directory)
        self._ensure_directory_exists()

    def _ensure_directory_exists(self) -> None:
        """Create notes directory if it doesn't exist."""
        self.notes_directory.mkdir(parents=True, exist_ok=True)

    def _get_note_path(self, note_id: str) -> Path:
        """Get the file path for a note by its ID."""
        return self.notes_directory / f"{note_id}.md"

    def save(self, note: Note) -> Note:
        """
        Save a note to disk.

        Args:
            note: The note to save.

        Returns:
            The saved note.
        """
        note.updated_at = datetime.now(timezone.utc)
        file_path = self._get_note_path(note.id)
        file_path.write_text(note.to_markdown(), encoding="utf-8")
        return note

    def get(self, note_id: str) -> Optional[Note]:
        """
        Retrieve a note by its ID.

        Args:
            note_id: The unique identifier of the note.

        Returns:
            The note if found, None otherwise.
        """
        file_path = self._get_note_path(note_id)
        if not file_path.exists():
            return None

        content = file_path.read_text(encoding="utf-8")
        return Note.from_markdown(content, note_id)

    def delete(self, note_id: str) -> bool:
        """
        Delete a note by its ID.

        Args:
            note_id: The unique identifier of the note.

        Returns:
            True if the note was deleted, False if it didn't exist.
        """
        file_path = self._get_note_path(note_id)
        if not file_path.exists():
            return False

        file_path.unlink()
        return True

    def list_all(
        self,
        tag: Optional[str] = None,
        limit: int = 100,
        offset: int = 0
    ) -> list[Note]:
        """
        List all notes, optionally filtered by tag.

        Args:
            tag: Optional tag to filter notes.
            limit: Maximum number of notes to return.
            offset: Number of notes to skip.

        Returns:
            List of notes matching the criteria.
        """
        notes = []

        for file_path in sorted(
            self.notes_directory.glob("*.md"),
            key=lambda p: p.stat().st_mtime,
            reverse=True
        ):
            note_id = file_path.stem
            note = self.get(note_id)
            if note:
                # Apply tag filter if specified
                if tag and tag not in note.tags:
                    continue
                notes.append(note)

        # Apply pagination
        return notes[offset:offset + limit]

    def search(
        self,
        query: str,
        tag: Optional[str] = None,
        limit: int = 20
    ) -> list[dict]:
        """
        Search notes by content and title.

        Args:
            query: Search query string.
            tag: Optional tag to filter results.
            limit: Maximum number of results.

        Returns:
            List of search results with context.
        """
        results = []
        query_lower = query.lower()

        for file_path in self.notes_directory.glob("*.md"):
            note_id = file_path.stem
            note = self.get(note_id)
            if not note:
                continue

            # Apply tag filter if specified
            if tag and tag not in note.tags:
                continue

            # Search in title and content
            title_match = query_lower in note.title.lower()
            content_lower = note.content.lower()
            content_match = query_lower in content_lower

            if title_match or content_match:
                # Extract context around the match
                context = self._extract_context(note.content, query, context_chars=100)

                results.append({
                    "note": note.to_dict(),
                    "match_in_title": title_match,
                    "match_in_content": content_match,
                    "context": context,
                })

                if len(results) >= limit:
                    break

        return results

    def _extract_context(
        self,
        content: str,
        query: str,
        context_chars: int = 100
    ) -> str:
        """Extract context around a search match."""
        content_lower = content.lower()
        query_lower = query.lower()

        pos = content_lower.find(query_lower)
        if pos == -1:
            # No match in content, return beginning of content
            return content[:context_chars * 2] + ("..." if len(content) > context_chars * 2 else "")

        # Calculate context boundaries
        start = max(0, pos - context_chars)
        end = min(len(content), pos + len(query) + context_chars)

        context = content[start:end]

        # Add ellipsis if truncated
        if start > 0:
            context = "..." + context
        if end < len(content):
            context = context + "..."

        return context

    def exists(self, note_id: str) -> bool:
        """Check if a note exists."""
        return self._get_note_path(note_id).exists()

    def count(self, tag: Optional[str] = None) -> int:
        """
        Count total notes, optionally filtered by tag.

        Args:
            tag: Optional tag to filter notes.

        Returns:
            Number of notes matching the criteria.
        """
        if tag is None:
            return len(list(self.notes_directory.glob("*.md")))

        count = 0
        for file_path in self.notes_directory.glob("*.md"):
            note = self.get(file_path.stem)
            if note and tag in note.tags:
                count += 1
        return count
