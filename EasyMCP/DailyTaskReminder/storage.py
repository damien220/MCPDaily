"""JSON file storage manager for tasks."""

from __future__ import annotations

import json
import uuid
import fcntl
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

from . import config


class TaskStorage:
    """CRUD operations on a JSON file of tasks.

    Auto-creates the storage directory and file on first use.
    Uses file locking (fcntl) to prevent corruption from concurrent access.
    """

    def __init__(self, path: Optional[Path] = None) -> None:
        self.path = path or config.STORAGE_PATH
        self._ensure_storage()

    # --- public API ---

    def add_task(
        self,
        title: str,
        description: str = "",
        due_at: Optional[str] = None,
        remind_at: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Create a new task and persist it. Returns the created task dict."""
        task = {
            "id": uuid.uuid4().hex[:8],
            "title": title,
            "description": description,
            "due_at": due_at,
            "remind_at": remind_at,
            "status": "pending",
            "notified": False,
            "created_at": datetime.now(timezone.utc).isoformat(),
        }
        tasks = self._load()
        tasks.append(task)
        self._save(tasks)
        return task

    def get_task(self, task_id: str) -> Optional[Dict[str, Any]]:
        """Return a single task by exact or prefix ID match, or None."""
        tasks = self._load()
        # Exact match first
        for t in tasks:
            if t["id"] == task_id:
                return t
        # Prefix match (at least 4 chars)
        if len(task_id) >= 4:
            matches = [t for t in tasks if t["id"].startswith(task_id)]
            if len(matches) == 1:
                return matches[0]
        return None

    def list_tasks(self, status_filter: str = "pending") -> List[Dict[str, Any]]:
        """Return tasks matching the filter.

        Filters: 'all', 'pending', 'completed', 'overdue'.
        """
        tasks = self._load()
        if status_filter == "all":
            return tasks
        if status_filter == "pending":
            return [t for t in tasks if t["status"] == "pending"]
        if status_filter == "completed":
            return [t for t in tasks if t["status"] == "completed"]
        if status_filter == "overdue":
            now = datetime.now(timezone.utc).isoformat()
            return [
                t for t in tasks
                if t["status"] == "pending" and t.get("due_at") and t["due_at"] < now
            ]
        return tasks

    def update_task(self, task_id: str, **fields: Any) -> Optional[Dict[str, Any]]:
        """Update fields on a task identified by exact or prefix ID.

        Returns the updated task, or None if not found.
        """
        tasks = self._load()
        task = self._find(tasks, task_id)
        if task is None:
            return None
        task.update(fields)
        self._save(tasks)
        return task

    def complete_task(self, task_id: str) -> Optional[Dict[str, Any]]:
        """Mark a task as completed. Returns the updated task or None."""
        return self.update_task(task_id, status="completed")

    def delete_task(self, task_id: str) -> Optional[Dict[str, Any]]:
        """Remove a task by ID. Returns the deleted task or None."""
        tasks = self._load()
        task = self._find(tasks, task_id)
        if task is None:
            return None
        tasks.remove(task)
        self._save(tasks)
        return task

    def get_due_reminders(self) -> List[Dict[str, Any]]:
        """Return pending tasks whose remind_at <= now and notified == False.

        Also marks them as notified and saves.
        """
        tasks = self._load()
        now = datetime.now(timezone.utc).isoformat()
        due = [
            t for t in tasks
            if t["status"] == "pending"
            and t.get("remind_at")
            and t["remind_at"] <= now
            and not t.get("notified", False)
        ]
        if due:
            for t in due:
                t["notified"] = True
            self._save(tasks)
        return due

    # --- internals ---

    def _ensure_storage(self) -> None:
        """Create the storage directory and file if they don't exist."""
        self.path.parent.mkdir(parents=True, exist_ok=True)
        if not self.path.exists():
            self._save([])

    def _load(self) -> List[Dict[str, Any]]:
        """Read tasks from the JSON file with a shared lock."""
        with open(self.path, "r", encoding="utf-8") as f:
            fcntl.flock(f, fcntl.LOCK_SH)
            try:
                data = json.load(f)
            except json.JSONDecodeError:
                data = []
            finally:
                fcntl.flock(f, fcntl.LOCK_UN)
        return data

    def _save(self, tasks: List[Dict[str, Any]]) -> None:
        """Write tasks to the JSON file with an exclusive lock."""
        with open(self.path, "w", encoding="utf-8") as f:
            fcntl.flock(f, fcntl.LOCK_EX)
            try:
                json.dump(tasks, f, indent=2)
                f.write("\n")
            finally:
                fcntl.flock(f, fcntl.LOCK_UN)

    @staticmethod
    def _find(tasks: List[Dict[str, Any]], task_id: str) -> Optional[Dict[str, Any]]:
        """Find a task by exact or prefix ID match."""
        for t in tasks:
            if t["id"] == task_id:
                return t
        if len(task_id) >= 4:
            matches = [t for t in tasks if t["id"].startswith(task_id)]
            if len(matches) == 1:
                return matches[0]
        return None
