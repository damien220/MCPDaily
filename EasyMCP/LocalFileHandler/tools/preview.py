"""PreviewTool — return the formatted name for a file/dir WITHOUT creating it."""

from __future__ import annotations

from pathlib import Path

from core.models import MCPRequest, MCPResponse
from core.tool_base import BaseTool

from ..naming import NameFormatter


class PreviewTool(BaseTool):
    """Preview what a name will become after naming rules are applied.

    Unlike CreateFileTool, nothing is written to disk — this is a pure
    read-only operation used by the web UI to show live naming previews.

    Payload:
        ``name``  (str, required) — raw user-provided name.
        ``type``  (str, optional) — file extension without dot (default "txt").
                                    Omit or set to "" for directory preview.

    Result:
        ``preview``        — path relative to workspace root.
        ``name``           — formatted filename/dirname.
        ``category``       — auto-detected category (or "").
        ``is_directory``   — True if type was omitted/empty.
    """

    def __init__(self, workspace: Path, formatter: NameFormatter, **kwargs):
        super().__init__(**kwargs)
        self.workspace = workspace
        self.formatter = formatter

    def handle(self, request: MCPRequest) -> MCPResponse:
        name = request.payload.get("name", "").strip()
        file_type = request.payload.get("type", "txt")

        if not name:
            return MCPResponse.failure(request, "Payload must include a 'name' field.")

        try:
            is_directory = not bool(file_type)

            if is_directory:
                path = self.formatter.ideal_filename(name, "")
                # For directories, use format_dirname-like preview
                from ..naming.rules import SanitizeRule, KebabCaseRule
                stem = name
                for rule in (SanitizeRule(), KebabCaseRule()):
                    stem = rule.apply(stem, {})
                preview_path = self.workspace / "projects" / stem
                return MCPResponse.success(
                    request,
                    {
                        "preview": str(preview_path.relative_to(self.workspace)) + "/",
                        "name": stem,
                        "category": "projects",
                        "is_directory": True,
                    },
                )

            extension = file_type if file_type.startswith(".") else f".{file_type}"
            ideal = self.formatter.ideal_filename(name, extension)

            # Determine the category from the target subdirectory
            try:
                relative = ideal.relative_to(self.workspace)
                category = relative.parts[0] if len(relative.parts) > 1 else ""
            except ValueError:
                category = ""

            return MCPResponse.success(
                request,
                {
                    "preview": str(ideal.relative_to(self.workspace)),
                    "name": ideal.name,
                    "category": category,
                    "is_directory": False,
                },
            )
        except Exception as e:
            return MCPResponse.failure(request, f"Preview failed: {e}")
