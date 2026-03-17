"""ConfigTool — view and modify naming rules and server config at runtime."""

from __future__ import annotations

from core.models import MCPRequest, MCPResponse
from core.tool_base import BaseTool

from ..config import Config
from ..naming import CategoryMap, NameFormatter

# Fields that can be toggled/changed via ConfigTool
_BOOL_FIELDS = {"date_prefix", "auto_categorize", "normalize_extensions"}
_STR_FIELDS = {"date_format", "case_style", "handle_duplicates"}


class ConfigTool(BaseTool):
    """View and modify the naming rules configuration at runtime.

    Actions:
        ``get``   — Return the current configuration (default).
        ``set``   — Update one or more naming rule fields.
        ``reset`` — Restore all naming rules to startup defaults.
        ``categories`` — List all extension→category mappings.
        ``add_category`` — Map a custom file extension to a category.
    """

    def __init__(
        self,
        config: Config,
        formatter: NameFormatter,
        category_map: CategoryMap,
        **kwargs,
    ):
        super().__init__(**kwargs)
        self._config = config
        self._formatter = formatter
        self._category_map = category_map
        # Snapshot defaults so we can reset
        self._defaults = {
            "date_prefix": config.naming.date_prefix,
            "date_format": config.naming.date_format,
            "auto_categorize": config.naming.auto_categorize,
            "normalize_extensions": config.naming.normalize_extensions,
            "case_style": config.naming.case_style,
            "handle_duplicates": config.naming.handle_duplicates,
        }

    # ------------------------------------------------------------------
    # Current state helpers
    # ------------------------------------------------------------------

    def _current_naming(self) -> dict:
        n = self._config.naming
        return {
            "date_prefix": n.date_prefix,
            "date_format": n.date_format,
            "auto_categorize": n.auto_categorize,
            "normalize_extensions": n.normalize_extensions,
            "case_style": n.case_style,
            "handle_duplicates": n.handle_duplicates,
        }

    def _sync_formatter(self) -> None:
        """Apply config values to the live NameFormatter."""
        n = self._config.naming
        self._formatter.date_format = n.date_format
        self._formatter.date_prefix_enabled = n.date_prefix
        self._formatter.auto_categorize = n.auto_categorize
        self._formatter.normalize_extensions = n.normalize_extensions

    # ------------------------------------------------------------------
    # handle
    # ------------------------------------------------------------------

    def handle(self, request: MCPRequest) -> MCPResponse:
        action: str = request.payload.get("action", "get").lower()

        if action == "get":
            return MCPResponse.success(
                request,
                {
                    "naming": self._current_naming(),
                    "workspace": str(self._config.workspace_path),
                    "server_host": self._config.server_host,
                    "server_port": self._config.server_port,
                    "trash_enabled": self._config.trash_enabled,
                    "trash_dir": self._config.trash_dir,
                },
            )

        if action == "set":
            updates = request.payload.get("values", {})
            if not updates:
                return MCPResponse.failure(
                    request, "Provide a 'values' dict with fields to update."
                )
            changed = {}
            errors = []
            n = self._config.naming
            for key, val in updates.items():
                if key in _BOOL_FIELDS:
                    if not isinstance(val, bool):
                        errors.append(f"'{key}' must be a boolean.")
                        continue
                    setattr(n, key, val)
                    changed[key] = val
                elif key in _STR_FIELDS:
                    if not isinstance(val, str):
                        errors.append(f"'{key}' must be a string.")
                        continue
                    setattr(n, key, val)
                    changed[key] = val
                else:
                    errors.append(f"Unknown or read-only field: '{key}'.")
            self._sync_formatter()
            result: dict = {"changed": changed}
            if errors:
                result["errors"] = errors
            result["current"] = self._current_naming()
            return MCPResponse.success(request, result)

        if action == "reset":
            n = self._config.naming
            for key, val in self._defaults.items():
                setattr(n, key, val)
            self._sync_formatter()
            return MCPResponse.success(
                request,
                {"reset": True, "current": self._current_naming()},
            )

        if action == "categories":
            cats = {}
            for ext, cat in self._category_map._categories.items():
                cats.setdefault(cat, []).append(ext)
            return MCPResponse.success(
                request, {"categories": cats, "total_extensions": len(self._category_map._categories)}
            )

        if action == "add_category":
            extension = request.payload.get("extension")
            category = request.payload.get("category")
            if not extension or not category:
                return MCPResponse.failure(
                    request, "Provide 'extension' and 'category' fields."
                )
            self._category_map.add_category(extension, category)
            return MCPResponse.success(
                request,
                {"added": {extension: category}},
            )

        return MCPResponse.failure(
            request,
            f"Unknown action '{action}'. Valid actions: get, set, reset, categories, add_category.",
        )
