"""SuggestionsTool — AI-powered workspace improvement suggestions.

Phase 4.4: Scans the workspace, gathers statistics (non-compliant names,
misplaced files, old files, large files, empty dirs, duplicate patterns),
formats a concise context document, and asks the LLM for 3–6 actionable
improvement suggestions with ready-to-execute tool calls.

When no AI backend is available the tool still returns rule-based suggestions
(non-compliant names, misplaced files) without LLM involvement.
"""

from __future__ import annotations

import re
import time
from pathlib import Path
from typing import TYPE_CHECKING

from core.models import MCPRequest, MCPResponse
from core.tool_base import BaseTool

if TYPE_CHECKING:
    from ..ai.client import AIClient

_SKIP_DIRS    = {".history", ".trash"}
_KEBAB_RE     = re.compile(r"^[\d]{4}-\d{2}-\d{2}_[a-z0-9]+(?:-[a-z0-9]+)*\.[a-z0-9]+$")
_SECONDS_OLD  = 90 * 86400   # 90 days

_SYSTEM = (
    "You are a professional file organisation consultant. "
    "You receive a summary of a user's workspace and must return JSON only — "
    "no markdown fences, no explanation outside the JSON."
)

_PROMPT_TMPL = """\
Workspace analysis:

{context}

Based on this analysis, provide 3-6 actionable improvement suggestions.
Return a JSON object in exactly this format:
{{
  "suggestions": [
    {{
      "type": "<rename|move|archive|organize|deduplicate|cleanup>",
      "priority": "<high|medium|low>",
      "description": "<plain-English description of the issue and fix>",
      "files": ["<path1>", "<path2>"],
      "action": {{
        "tool": "<tool_name or null>",
        "payload": {{}}
      }}
    }}
  ]
}}
Rules:
- Keep descriptions concise (≤ 2 sentences).
- Only include suggestions that add clear value.
- For organize suggestions always set dry_run: true in the payload.
- Set action.tool to null when no single tool call covers the suggestion.
"""


def _human_size(b: int) -> str:
    for unit in ("B", "KB", "MB", "GB"):
        if b < 1024:
            return f"{b:.1f} {unit}"
        b //= 1024
    return f"{b:.1f} TB"


class SuggestionsTool(BaseTool):
    """AI-powered suggestions for improving workspace organisation.

    Payload:
        ``path``  (str, optional, default ".")  — sub-directory to analyse.

    Result (success):
        ``suggestions``  — list of suggestion objects, each with:
            ``type``        — rename | move | archive | organize | deduplicate | cleanup
            ``priority``    — high | medium | low
            ``description`` — plain-English description
            ``files``       — list of affected file paths
            ``action``      — {tool, payload} ready to POST to /invoke (or null)
        ``stats``        — workspace statistics used to generate suggestions
        ``ai_backend``   — which backend was used (or "rule-based")
    """

    def __init__(self, workspace: Path, client: "AIClient", **kwargs) -> None:
        super().__init__(**kwargs)
        self.workspace = workspace
        self.client = client

    def handle(self, request: MCPRequest) -> MCPResponse:
        rel = request.payload.get("path", ".").strip() or "."

        scan_root = (self.workspace / rel).resolve()
        if not str(scan_root).startswith(str(self.workspace.resolve())):
            return MCPResponse.failure(request, "Path escapes workspace.")
        if not scan_root.exists():
            return MCPResponse.failure(request, f"Path not found: {rel}")

        stats, issues = self._analyse(scan_root)

        if self.client.available:
            context = self._build_context(stats, issues)
            prompt  = _PROMPT_TMPL.format(context=context)
            parsed  = self.client.ask_json(prompt, system=_SYSTEM, max_tokens=1024)

            if parsed and "suggestions" in parsed:
                return MCPResponse.success(request, {
                    "suggestions": parsed["suggestions"],
                    "stats":       stats,
                    "ai_backend":  self.client.backend_name,
                })
            # Fall through to rule-based on parse failure

        # Rule-based fallback
        suggestions = self._rule_based_suggestions(issues)
        return MCPResponse.success(request, {
            "suggestions": suggestions,
            "stats":       stats,
            "ai_backend":  "rule-based",
        })

    # ── Analysis helpers ──────────────────────────────────────────────────────

    def _analyse(self, root: Path) -> tuple[dict, dict]:
        """Walk *root* and collect workspace statistics and issue lists."""
        now = time.time()

        total_files  = 0
        total_size   = 0
        old_files:       list[str] = []
        non_compliant:   list[str] = []
        large_files:     list[tuple[str, int]] = []
        empty_dirs:      list[str] = []
        cat_counts:      dict[str, int] = {}

        for p in root.rglob("*"):
            if any(part in _SKIP_DIRS for part in p.parts):
                continue

            if p.is_dir():
                children = [c for c in p.iterdir()
                            if c.name not in _SKIP_DIRS]
                if not children:
                    empty_dirs.append(str(p.relative_to(self.workspace)))
                continue

            # It's a file
            total_files += 1
            try:
                st = p.stat()
            except OSError:
                continue

            size = st.st_size
            total_size += size
            rel = str(p.relative_to(self.workspace))

            # Category count (top-level dir)
            parts = p.relative_to(root).parts
            cat = parts[0] if len(parts) > 1 else "(root)"
            cat_counts[cat] = cat_counts.get(cat, 0) + 1

            # Non-compliant naming (heuristic: not kebab, has uppercase or spaces)
            name = p.name
            if " " in name or any(c.isupper() for c in name):
                non_compliant.append(rel)

            # Old files (≥ 90 days since last modification)
            if (now - st.st_mtime) >= _SECONDS_OLD:
                old_files.append(rel)

            # Large files (> 50 MB)
            if size > 50 * 1024 * 1024:
                large_files.append((rel, size))

        stats = {
            "total_files":  total_files,
            "total_size":   _human_size(total_size),
            "by_category":  cat_counts,
            "old_files":    len(old_files),
            "empty_dirs":   len(empty_dirs),
            "large_files":  len(large_files),
            "non_compliant": len(non_compliant),
        }
        issues = {
            "old_files":    old_files[:10],
            "non_compliant": non_compliant[:10],
            "large_files":  [f"{p} ({_human_size(s)})" for p, s in large_files[:5]],
            "empty_dirs":   empty_dirs[:5],
        }
        return stats, issues

    def _build_context(self, stats: dict, issues: dict) -> str:
        lines = [
            f"Total files: {stats['total_files']}  |  Total size: {stats['total_size']}",
            f"Non-compliant names: {stats['non_compliant']}",
            f"Old files (≥90 days): {stats['old_files']}",
            f"Large files (>50MB): {stats['large_files']}",
            f"Empty directories: {stats['empty_dirs']}",
        ]
        if stats["by_category"]:
            cats = ", ".join(f"{k}={v}" for k, v in stats["by_category"].items())
            lines.append(f"Files by category: {cats}")
        for key, label in (
            ("non_compliant", "Non-compliant files (sample)"),
            ("old_files",     "Old files (sample)"),
            ("large_files",   "Large files"),
            ("empty_dirs",    "Empty directories"),
        ):
            items = issues.get(key, [])
            if items:
                lines.append(f"\n{label}:")
                lines.extend(f"  - {i}" for i in items)
        return "\n".join(lines)

    def _rule_based_suggestions(self, issues: dict) -> list[dict]:
        suggestions: list[dict] = []

        if issues["non_compliant"]:
            suggestions.append({
                "type":        "rename",
                "priority":    "medium",
                "description": (
                    f"{len(issues['non_compliant'])} file(s) have non-compliant names "
                    "(spaces or uppercase). Run Organize to auto-rename them."
                ),
                "files":  issues["non_compliant"][:5],
                "action": {"tool": "organizetool", "payload": {"path": ".", "dry_run": True}},
            })

        if issues["old_files"]:
            suggestions.append({
                "type":        "archive",
                "priority":    "low",
                "description": (
                    f"{len(issues['old_files'])} file(s) haven't been modified in "
                    "over 90 days. Consider archiving or deleting unused files."
                ),
                "files":  issues["old_files"][:5],
                "action": {"tool": None, "payload": {}},
            })

        if issues["empty_dirs"]:
            suggestions.append({
                "type":        "cleanup",
                "priority":    "low",
                "description": (
                    f"{len(issues['empty_dirs'])} empty director(y/ies) found. "
                    "Remove them to keep the workspace tidy."
                ),
                "files":  issues["empty_dirs"],
                "action": {"tool": None, "payload": {}},
            })

        if not suggestions:
            suggestions.append({
                "type":        "organize",
                "priority":    "low",
                "description": "Workspace looks clean! Run Organize periodically to keep it that way.",
                "files":       [],
                "action":      {"tool": "organizetool", "payload": {"path": ".", "dry_run": True}},
            })

        return suggestions
