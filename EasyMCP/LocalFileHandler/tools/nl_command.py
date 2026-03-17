"""NLCommandTool — natural-language interface to LocalFileHandler tools.

Phase 4.2: Users send a plain-English command; the LLM resolves it to a
concrete tool + payload that the caller can then execute via a second
POST /invoke.  This is intentionally a *parse-only* step — the tool never
auto-executes destructive operations without explicit user confirmation.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from core.models import MCPRequest, MCPResponse
from core.tool_base import BaseTool

if TYPE_CHECKING:
    from ..ai.client import AIClient

_SYSTEM = """\
You are a file management assistant for LocalFileHandler.
Given a natural-language command from the user, return a single JSON object that
maps the command to one of the available tools.

Available tools and their payloads:

createfiletool      — create a new file
  payload: {name: str, type: str (extension without dot, e.g. md/txt/py/json), content: str (optional)}

createdirtool       — create a new directory / folder
  payload: {name: str}

listcontentstool    — list files in a directory
  payload: {path: str (default "."), recursive: bool (optional)}

renametool          — rename a file or folder
  payload: {path: str (relative), new_name: str}

movetool            — move a file or folder to another directory
  payload: {source: str (relative), destination: str (relative dir path ending with /)}

deletetool          — delete a file or folder (moves to trash)
  payload: {path: str (relative), confirm: true}

searchtool          — search for files by name/type/date
  payload: {query: str, type: str (optional ext), path: str (optional), date_from: str YYYY-MM-DD (optional)}

organizetool        — reorganise a directory by naming rules
  payload: {path: str (default "."), dry_run: bool (default true — ALWAYS use true unless the user explicitly says "apply" or "execute")}

historytool         — retrieve recent operation history
  payload: {limit: int (default 15)}

undotool            — undo the last N operations
  payload: {steps: int (default 1)}

smartcategorizetool — AI-categorise a file by reading its content
  payload: {path: str, apply: bool (default false)}

duplicatestool      — find exact and near-duplicate files
  payload: {path: str (default "."), mode: str (exact|similar|all, default all)}

suggestionstool     — get AI workspace improvement suggestions
  payload: {path: str (default ".")}

Rules:
- Choose the most specific tool.
- For destructive operations (delete, overwrite) set requires_confirmation: true.
- For organize without explicit "apply/execute": always use dry_run: true.
- Return ONLY a JSON object — no markdown fences, no extra text.

Response format:
{
  "tool": "<tool_name>",
  "payload": { ... },
  "explanation": "<one sentence describing what will happen>",
  "requires_confirmation": <true|false>
}

If the command cannot be mapped to any tool, return:
{"error": "<reason why the command cannot be processed>"}
"""


class NLCommandTool(BaseTool):
    """Parse a natural-language file management command into a tool call.

    The tool does **not** execute the resolved command — it only returns the
    parsed ``{tool, payload, explanation, requires_confirmation}`` object.
    The client (web UI or API consumer) is responsible for executing the
    returned tool call after any required confirmation step.

    Payload:
        ``command``  (str, required) — plain-English instruction, e.g.
                     "Create a meeting notes file for today".

    Result (success):
        ``tool``                  — target tool name
        ``payload``               — ready-to-use payload dict
        ``explanation``           — one-sentence description
        ``requires_confirmation`` — True if the operation is destructive
        ``ai_backend``            — which backend resolved the command

    Result (error):
        ``error`` with a human-readable explanation when the command cannot
        be mapped, the AI backend is unavailable, or parsing fails.
    """

    def __init__(self, client: "AIClient", **kwargs) -> None:
        super().__init__(**kwargs)
        self.client = client

    def handle(self, request: MCPRequest) -> MCPResponse:
        command = request.payload.get("command", "").strip()
        if not command:
            return MCPResponse.failure(request, "Payload must include a 'command' string.")

        if not self.client.available:
            return MCPResponse.failure(
                request,
                "AI backend is not configured. Set ANTHROPIC_API_KEY, or start an "
                "Ollama/llama.cpp server and set AI_BACKEND in your .env file.",
            )

        result = self.client.ask_json(command, system=_SYSTEM, max_tokens=512)

        if result is None:
            return MCPResponse.failure(
                request,
                "AI backend returned an unparseable response. Please try rephrasing "
                "your command.",
            )

        if "error" in result:
            return MCPResponse.failure(request, result["error"])

        if "tool" not in result:
            return MCPResponse.failure(
                request,
                "AI response is missing the 'tool' field. Please try rephrasing.",
            )

        return MCPResponse.success(request, {
            "tool":                   result.get("tool"),
            "payload":                result.get("payload", {}),
            "explanation":            result.get("explanation", ""),
            "requires_confirmation":  bool(result.get("requires_confirmation", False)),
            "ai_backend":             self.client.backend_name,
        })
