"""OrganizeTool — bulk-organize files by applying naming rules to a directory."""

from __future__ import annotations

import shutil
from pathlib import Path

from core.models import MCPRequest, MCPResponse
from core.tool_base import BaseTool

from ..history import Operation, OperationLog
from ..naming import NameFormatter


class OrganizeTool(BaseTool):
    """Scan a directory and reorganize its files according to the naming rules.

    Supports dry-run mode (preview only) and logs a single reversible operation
    that can be undone in bulk by UndoTool.
    """

    def __init__(
        self,
        workspace: Path,
        formatter: NameFormatter,
        operation_log: OperationLog | None = None,
        **kwargs,
    ):
        super().__init__(**kwargs)
        self.workspace = workspace
        self.formatter = formatter
        self.operation_log = operation_log

    def _safe_path(self, user_path: str) -> Path | None:
        resolved = (self.workspace / user_path).resolve()
        if not str(resolved).startswith(str(self.workspace.resolve())):
            return None
        return resolved

    def handle(self, request: MCPRequest) -> MCPResponse:
        path_str: str = request.payload.get("path", ".")
        dry_run: bool = request.payload.get("dry_run", True)

        target = self._safe_path(path_str)
        if target is None:
            return MCPResponse.failure(request, "Path is outside the workspace.")
        if not target.exists():
            return MCPResponse.failure(request, f"Path does not exist: {path_str}")
        if not target.is_dir():
            return MCPResponse.failure(request, f"Path is not a directory: {path_str}")

        try:
            planned_moves: list[dict] = []
            executed_moves: list[dict] = []
            skipped: list[dict] = []

            for item in sorted(target.rglob("*")):
                if not item.is_file():
                    continue

                # Skip files in hidden system directories
                rel = item.relative_to(self.workspace)
                if any(part.startswith(".") for part in rel.parts):
                    continue

                raw_stem = item.stem
                extension = item.suffix

                # First check compliance without duplicate detection
                ideal = self.formatter.ideal_filename(raw_stem, extension)
                if ideal.resolve() == item.resolve():
                    skipped.append({
                        "path": str(rel),
                        "reason": "already_compliant",
                    })
                    continue

                # Compute the actual new path (with duplicate handling)
                new_path, rules_applied = self.formatter.format_filename(
                    raw_stem, extension
                )

                move_entry = {
                    "from": str(item.relative_to(self.workspace)),
                    "to": str(new_path.relative_to(self.workspace)),
                    "rules_applied": rules_applied,
                }
                planned_moves.append(move_entry)

                if not dry_run:
                    new_path.parent.mkdir(parents=True, exist_ok=True)
                    if new_path.exists():
                        skipped.append({
                            "path": str(rel),
                            "reason": "target_exists",
                            "target": str(new_path.relative_to(self.workspace)),
                        })
                        continue
                    shutil.move(str(item), str(new_path))
                    executed_moves.append(move_entry)

            result = {
                "path": path_str,
                "dry_run": dry_run,
                "planned": len(planned_moves),
                "executed": len(executed_moves),
                "skipped": len(skipped),
                "moves": planned_moves if dry_run else executed_moves,
                "skipped_details": skipped,
            }
            response = MCPResponse.success(request, result)

            if self.operation_log and not dry_run and executed_moves:
                # Build undo_data to reverse all moves at once
                undo_moves = [
                    {"from_path": m["to"], "to_path": m["from"]}
                    for m in executed_moves
                ]
                self.operation_log.record(
                    Operation(
                        tool=self.name,
                        status="success",
                        payload=dict(request.payload),
                        result=result,
                        undoable=True,
                        undo_data={
                            "action": "undo_organize",
                            "workspace": str(self.workspace),
                            "moves": undo_moves,
                        },
                        request_id=request.id,
                    )
                )
            return response
        except Exception as e:
            return MCPResponse.failure(request, f"Organize failed: {e}")
