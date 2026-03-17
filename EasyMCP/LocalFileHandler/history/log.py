"""OperationLog — persistent JSON-lines log of all file operations."""

from __future__ import annotations

import json
from pathlib import Path
from threading import Lock

from .models import Operation


class OperationLog:
    """Thread-safe append-only log stored as JSON lines.

    Each line in the log file is a complete JSON object representing one
    Operation.  The log is read fresh from disk on every query so that
    multiple processes (CLI + HTTP) share the same history file safely.

    Args:
        log_path: Path to the ``operations.jsonl`` file.  Parent directories
            are created automatically.
    """

    def __init__(self, log_path: Path) -> None:
        self.log_path = log_path
        self.log_path.parent.mkdir(parents=True, exist_ok=True)
        self._lock = Lock()

    # ------------------------------------------------------------------
    # Writing
    # ------------------------------------------------------------------

    def record(self, op: Operation) -> None:
        """Append an operation to the log (thread-safe)."""
        with self._lock:
            with self.log_path.open("a", encoding="utf-8") as fh:
                fh.write(json.dumps(op.to_dict()) + "\n")

    def mark_undone(self, op_id: str) -> bool:
        """Mark an operation as undone by rewriting the log file.

        Returns True if the operation was found and marked, False otherwise.
        """
        with self._lock:
            ops = self._read_all_raw()
            found = False
            for entry in ops:
                if entry.get("id") == op_id:
                    entry["undone"] = True
                    found = True
                    break
            if found:
                self._write_all_raw(ops)
            return found

    # ------------------------------------------------------------------
    # Reading
    # ------------------------------------------------------------------

    def all_operations(self) -> list[Operation]:
        """Return all recorded operations (oldest first)."""
        with self._lock:
            return [Operation.from_dict(d) for d in self._read_all_raw()]

    def get_recent(
        self,
        limit: int = 20,
        tool_filter: str | None = None,
        status_filter: str | None = None,
    ) -> list[Operation]:
        """Return the most recent *limit* operations, newest first.

        Args:
            limit: Maximum number of operations to return.
            tool_filter: If set, only return operations from this tool.
            status_filter: If set, only return operations with this status
                (``"success"`` or ``"error"``).
        """
        ops = self.all_operations()
        if tool_filter:
            ops = [o for o in ops if o.tool == tool_filter]
        if status_filter:
            ops = [o for o in ops if o.status == status_filter]
        return list(reversed(ops))[:limit]

    def get_by_id(self, op_id: str) -> Operation | None:
        """Look up a single operation by its UUID."""
        for op in self.all_operations():
            if op.id == op_id:
                return op
        return None

    def last_undoable(self) -> Operation | None:
        """Return the most recent undoable, not-yet-undone operation."""
        for op in reversed(self.all_operations()):
            if op.undoable and not op.undone and op.status == "success":
                return op
        return None

    def undoable_stack(self, limit: int = 10) -> list[Operation]:
        """Return up to *limit* undoable operations (newest first)."""
        candidates = [
            op
            for op in reversed(self.all_operations())
            if op.undoable and not op.undone and op.status == "success"
        ]
        return candidates[:limit]

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _read_all_raw(self) -> list[dict]:
        if not self.log_path.exists():
            return []
        lines = []
        with self.log_path.open("r", encoding="utf-8") as fh:
            for line in fh:
                line = line.strip()
                if line:
                    try:
                        lines.append(json.loads(line))
                    except json.JSONDecodeError:
                        pass  # skip corrupt lines
        return lines

    def _write_all_raw(self, ops: list[dict]) -> None:
        with self.log_path.open("w", encoding="utf-8") as fh:
            for entry in ops:
                fh.write(json.dumps(entry) + "\n")
