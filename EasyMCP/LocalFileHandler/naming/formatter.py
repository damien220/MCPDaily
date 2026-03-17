"""NameFormatter — applies a pipeline of naming rules to produce compliant names."""

from __future__ import annotations

from pathlib import Path

from .categories import CategoryMap
from .rules import (
    DatePrefixRule,
    DuplicateRule,
    ExtensionNormalizeRule,
    KebabCaseRule,
    NamingRule,
    SanitizeRule,
)


class NameFormatter:
    """Applies a configurable pipeline of naming rules to file/directory names.

    Args:
        workspace: Root workspace path (used for duplicate detection).
        category_map: CategoryMap instance for extension-based categorization.
        date_format: strftime format string for date prefix.
        date_prefix: Whether to add a date prefix.
        auto_categorize: Whether to auto-sort into category subdirectories.
        normalize_extensions: Whether to normalize file extensions.
    """

    def __init__(
        self,
        workspace: Path,
        category_map: CategoryMap | None = None,
        date_format: str = "%Y-%m-%d",
        date_prefix: bool = True,
        auto_categorize: bool = True,
        normalize_extensions: bool = True,
    ):
        self.workspace = workspace
        self.category_map = category_map or CategoryMap()
        self.date_format = date_format
        self.date_prefix_enabled = date_prefix
        self.auto_categorize = auto_categorize
        self.normalize_extensions = normalize_extensions

    def _build_pipeline(self, is_directory: bool = False) -> list[NamingRule]:
        """Build the rule pipeline based on current configuration."""
        rules: list[NamingRule] = [SanitizeRule(), KebabCaseRule()]
        if self.normalize_extensions and not is_directory:
            rules.append(ExtensionNormalizeRule())
        if self.date_prefix_enabled and not is_directory:
            rules.append(DatePrefixRule())
        rules.append(DuplicateRule())
        return rules

    def ideal_filename(self, raw_name: str, extension: str = "") -> Path:
        """Compute the 'ideal' compliant path without duplicate detection.

        Used by OrganizeTool to check whether a file is already in the right
        location before deciding to move it.
        """
        if not extension.startswith(".") and extension:
            extension = f".{extension}"
        ctx = self._make_context(extension=extension, is_directory=False)
        rules = self._build_pipeline(is_directory=False)
        # Run all rules except DuplicateRule
        stem = raw_name
        for rule in rules:
            if rule.name == "duplicate":
                continue
            rule.apply(stem, ctx)
            stem = rule.apply(stem, ctx)
        extension = ctx.get("extension", extension)
        target_dir = self._resolve_category_dir(extension)
        return target_dir / f"{stem}{extension}"

    def format_filename(
        self, raw_name: str, extension: str = ""
    ) -> tuple[Path, list[str]]:
        """Format a raw filename through the naming pipeline.

        Args:
            raw_name: The user-provided filename (without extension).
            extension: The file extension (e.g. ".md", ".txt").

        Returns:
            A tuple of (full_path relative to workspace, list of rule names applied).
        """
        if not extension.startswith(".") and extension:
            extension = f".{extension}"

        ctx = self._make_context(extension=extension, is_directory=False)
        rules = self._build_pipeline(is_directory=False)

        stem = raw_name
        applied: list[str] = []
        for rule in rules:
            old = stem
            old_ext = ctx.get("extension", "")
            stem = rule.apply(stem, ctx)
            if stem != old or ctx.get("extension", "") != old_ext:
                applied.append(rule.name)

        extension = ctx.get("extension", extension)

        # Determine target directory (category-based or workspace root)
        target_dir = self._resolve_category_dir(extension)
        ctx["target_dir"] = target_dir

        # Re-run duplicate rule with the correct target directory
        dup_rule = DuplicateRule()
        old_stem = stem
        stem = dup_rule.apply(stem, ctx)
        if stem != old_stem and "duplicate" not in applied:
            applied.append("duplicate")

        target_dir.mkdir(parents=True, exist_ok=True)
        full_path = target_dir / f"{stem}{extension}"
        return full_path, applied

    def format_dirname(self, raw_name: str) -> tuple[Path, list[str]]:
        """Format a raw directory name through the naming pipeline.

        Returns:
            A tuple of (full_path relative to workspace, list of rule names applied).
        """
        target_dir = self.workspace / "projects"
        ctx = self._make_context(
            extension="", is_directory=True, target_dir=target_dir
        )
        rules = self._build_pipeline(is_directory=True)

        stem = raw_name
        applied: list[str] = []
        for rule in rules:
            old = stem
            stem = rule.apply(stem, ctx)
            if stem != old:
                applied.append(rule.name)

        target_dir.mkdir(parents=True, exist_ok=True)
        full_path = target_dir / stem
        return full_path, applied

    def format_rename(
        self, new_name: str, extension: str = ""
    ) -> tuple[str, str, list[str]]:
        """Format a new name for renaming (returns stem + extension + rules applied).

        Does NOT check duplicates — caller handles that with actual target path.
        """
        if not extension.startswith(".") and extension:
            extension = f".{extension}"

        ctx = self._make_context(extension=extension, is_directory=False)
        # Only sanitize + kebab + extension normalize for renames
        rules: list[NamingRule] = [SanitizeRule(), KebabCaseRule()]
        if self.normalize_extensions:
            rules.append(ExtensionNormalizeRule())

        stem = new_name
        applied: list[str] = []
        for rule in rules:
            old = stem
            old_ext = ctx.get("extension", "")
            stem = rule.apply(stem, ctx)
            if stem != old or ctx.get("extension", "") != old_ext:
                applied.append(rule.name)

        extension = ctx.get("extension", extension)
        return stem, extension, applied

    def _resolve_category_dir(self, extension: str) -> Path:
        """Determine the target subdirectory based on file extension category."""
        if not self.auto_categorize or not extension:
            return self.workspace
        category = self.category_map.get_category(extension)
        if category:
            return self.workspace / category
        return self.workspace

    def _make_context(
        self,
        extension: str = "",
        is_directory: bool = False,
        target_dir: Path | None = None,
    ) -> dict:
        return {
            "extension": extension,
            "workspace": self.workspace,
            "target_dir": target_dir or self.workspace,
            "is_directory": is_directory,
            "date_format": self.date_format,
            "category_map": self.category_map,
        }
