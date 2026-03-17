"""SmartCategorizeTool — AI-powered content-based file categorization.

Phase 4.1: Beyond the extension-based ``CategoryMap``, this tool reads the
actual *content* of a file and calls an LLM to suggest the most appropriate
category and descriptive tags.  It can also apply the categorization by moving
the file to the correct sub-directory.
"""

from __future__ import annotations

import json
import shutil
from pathlib import Path
from typing import TYPE_CHECKING

from core.models import MCPRequest, MCPResponse
from core.tool_base import BaseTool

if TYPE_CHECKING:
    from ..ai.client import AIClient

# Extensions whose content is readable as text
_TEXT_EXTENSIONS = {
    ".txt", ".md", ".py", ".js", ".ts", ".html", ".css", ".json", ".yaml",
    ".yml", ".toml", ".csv", ".xml", ".sh", ".bash", ".rst", ".tex", ".log",
    ".cfg", ".ini", ".env", ".sql", ".r", ".rb", ".go", ".rs", ".c", ".cpp",
    ".h", ".java", ".kt", ".swift", ".php",
}
_READ_BYTES = 1200    # characters of content to send to the LLM

_SYSTEM = (
    "You are a file management assistant. Your job is to categorise files based "
    "on their name and content. Always respond with valid JSON only — no markdown, "
    "no explanation outside the JSON object."
)

_PROMPT_TMPL = """\
File name: {name}
File extension: {ext}
Content preview (first {n} chars):
---
{content}
---

Respond with a JSON object in exactly this format:
{{
  "category": "<one of: documents, spreadsheets, images, videos, audio, code, data, archives, notes, other>",
  "tags": ["<tag1>", "<tag2>"],
  "confidence": "<high|medium|low>",
  "reason": "<one sentence explaining the categorisation>"
}}
"""


class SmartCategorizeTool(BaseTool):
    """AI-powered content-based file categorisation.

    Payload:
        ``path``    (str, required) — path relative to workspace root.
        ``apply``   (bool, optional, default False) — if True, move the file
                    to the suggested category sub-directory.

    Result (success):
        ``path``        — original path
        ``category``    — suggested category name
        ``tags``        — list of descriptive tags
        ``confidence``  — high | medium | low
        ``reason``      — one-sentence explanation
        ``applied``     — True if the file was actually moved
        ``new_path``    — new path if applied, else null
        ``ai_backend``  — which backend was used (or "rule-based")
    """

    def __init__(self, workspace: Path, client: "AIClient", **kwargs) -> None:
        super().__init__(**kwargs)
        self.workspace = workspace
        self.client = client

    def handle(self, request: MCPRequest) -> MCPResponse:
        rel = request.payload.get("path", "").strip()
        apply = bool(request.payload.get("apply", False))

        if not rel:
            return MCPResponse.failure(request, "Payload must include 'path'.")

        abs_path = (self.workspace / rel).resolve()

        # Security: must stay inside workspace
        if not str(abs_path).startswith(str(self.workspace.resolve())):
            return MCPResponse.failure(request, "Path escapes workspace.")

        if not abs_path.exists():
            return MCPResponse.failure(request, f"Path not found: {rel}")
        if abs_path.is_dir():
            return MCPResponse.failure(request, "SmartCategorizeTool works on files, not directories.")

        # ── Read content preview ─────────────────────────────────────────
        content = ""
        if abs_path.suffix.lower() in _TEXT_EXTENSIONS:
            try:
                raw = abs_path.read_bytes()
                content = raw.decode("utf-8", errors="replace")[:_READ_BYTES]
            except Exception:
                content = ""

        # ── Ask LLM ──────────────────────────────────────────────────────
        if self.client.available:
            prompt = _PROMPT_TMPL.format(
                name=abs_path.name,
                ext=abs_path.suffix or "(none)",
                n=_READ_BYTES,
                content=content or "(binary or unreadable content)",
            )
            result = self.client.ask_json(prompt, system=_SYSTEM, max_tokens=300)

            if result and "category" in result:
                category    = result.get("category", "other")
                tags        = result.get("tags", [])
                confidence  = result.get("confidence", "medium")
                reason      = result.get("reason", "")
                backend     = self.client.backend_name
            else:
                # LLM returned bad JSON — fall back to extension-based rule
                return self._rule_based(request, abs_path, rel, apply)
        else:
            return self._rule_based(request, abs_path, rel, apply)

        # ── Optionally apply ─────────────────────────────────────────────
        applied  = False
        new_path = None
        if apply:
            target_dir = self.workspace / category
            target_dir.mkdir(parents=True, exist_ok=True)
            target = target_dir / abs_path.name
            if target != abs_path:
                if target.exists():
                    return MCPResponse.failure(
                        request,
                        f"Cannot move: '{category}/{abs_path.name}' already exists.",
                    )
                shutil.move(str(abs_path), str(target))
                applied  = True
                new_path = str(target.relative_to(self.workspace))

        return MCPResponse.success(request, {
            "path":       rel,
            "category":   category,
            "tags":       tags,
            "confidence": confidence,
            "reason":     reason,
            "applied":    applied,
            "new_path":   new_path,
            "ai_backend": backend,
        })

    # ── Fallback: extension-only categorisation ───────────────────────────
    _EXT_MAP = {
        "documents":    {".pdf", ".doc", ".docx", ".odt", ".txt", ".md", ".rtf"},
        "spreadsheets": {".xls", ".xlsx", ".csv", ".ods"},
        "images":       {".jpg", ".jpeg", ".png", ".gif", ".svg", ".webp", ".bmp"},
        "videos":       {".mp4", ".avi", ".mkv", ".mov", ".webm"},
        "audio":        {".mp3", ".wav", ".flac", ".ogg", ".m4a"},
        "code":         {".py", ".js", ".ts", ".go", ".rs", ".c", ".cpp", ".h",
                         ".java", ".kt", ".rb", ".php", ".sh", ".html", ".css"},
        "data":         {".json", ".yaml", ".yml", ".toml", ".xml", ".sql"},
        "archives":     {".zip", ".tar", ".gz", ".bz2", ".rar", ".7z"},
    }

    def _rule_based(
        self,
        request: MCPRequest,
        abs_path: Path,
        rel: str,
        apply: bool,
    ) -> MCPResponse:
        ext = abs_path.suffix.lower()
        category = "other"
        for cat, exts in self._EXT_MAP.items():
            if ext in exts:
                category = cat
                break

        applied  = False
        new_path = None
        if apply:
            target_dir = self.workspace / category
            target_dir.mkdir(parents=True, exist_ok=True)
            target = target_dir / abs_path.name
            if target != abs_path and not target.exists():
                shutil.move(str(abs_path), str(target))
                applied  = True
                new_path = str(target.relative_to(self.workspace))

        return MCPResponse.success(request, {
            "path":       rel,
            "category":   category,
            "tags":       [],
            "confidence": "medium",
            "reason":     "Categorised by file extension (AI backend unavailable).",
            "applied":    applied,
            "new_path":   new_path,
            "ai_backend": "rule-based",
        })
