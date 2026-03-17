"""Naming rules that transform raw names into compliant filenames/dirnames."""

from __future__ import annotations

import re
from abc import ABC, abstractmethod
from datetime import datetime
from pathlib import Path

from .categories import CategoryMap


class NamingRule(ABC):
    """Base class for all naming rules."""

    name: str = "base"

    @abstractmethod
    def apply(self, stem: str, ctx: dict) -> str:
        """Transform the stem (filename without extension).

        Args:
            stem: The current filename stem.
            ctx: Shared context dict with keys like 'extension', 'workspace',
                 'is_directory', 'date_format', etc.

        Returns:
            The transformed stem.
        """


class SanitizeRule(NamingRule):
    """Remove or replace special characters that are unsafe in filenames."""

    name = "sanitize"

    # Characters to strip entirely
    _STRIP = re.compile(r"[<>:\"/\\|?*\x00-\x1f]")
    # Collapse whitespace and dashes
    _COLLAPSE = re.compile(r"[-\s]+")

    def apply(self, stem: str, ctx: dict) -> str:
        result = self._STRIP.sub("", stem)
        # Replace parentheses and brackets with nothing (collapse later)
        result = re.sub(r"[(){}\[\]]", " ", result)
        result = result.strip()
        result = self._COLLAPSE.sub("-", result)
        result = result.strip("-")
        return result


class KebabCaseRule(NamingRule):
    """Convert the stem to kebab-case (lowercase, hyphen-separated)."""

    name = "kebab_case"

    def apply(self, stem: str, ctx: dict) -> str:
        # Insert hyphens before uppercase letters (camelCase → camel-Case)
        result = re.sub(r"([a-z0-9])([A-Z])", r"\1-\2", stem)
        # Replace underscores and spaces with hyphens
        result = re.sub(r"[_\s]+", "-", result)
        # Collapse multiple hyphens
        result = re.sub(r"-+", "-", result)
        return result.lower().strip("-")


class DatePrefixRule(NamingRule):
    """Prepend a date prefix to the stem."""

    name = "date_prefix"

    def apply(self, stem: str, ctx: dict) -> str:
        date_format = ctx.get("date_format", "%Y-%m-%d")
        prefix = datetime.now().strftime(date_format)
        # Don't double-add if stem already starts with a date-like prefix
        if stem.startswith(prefix):
            return stem
        return f"{prefix}_{stem}"


class ExtensionNormalizeRule(NamingRule):
    """Normalize file extensions (e.g. .JPEG → .jpg)."""

    name = "extension_normalize"

    def apply(self, stem: str, ctx: dict) -> str:
        category_map: CategoryMap | None = ctx.get("category_map")
        extension = ctx.get("extension", "")
        if extension and category_map:
            ctx["extension"] = category_map.normalize_extension(extension)
        return stem


class DuplicateRule(NamingRule):
    """Handle duplicate filenames by appending an incrementing suffix."""

    name = "duplicate"

    def apply(self, stem: str, ctx: dict) -> str:
        workspace: Path | None = ctx.get("target_dir")
        extension = ctx.get("extension", "")
        is_directory = ctx.get("is_directory", False)

        if workspace is None:
            return stem

        if is_directory:
            candidate = workspace / stem
        else:
            candidate = workspace / f"{stem}{extension}"

        if not candidate.exists():
            return stem

        # Find next available number
        counter = 2
        while True:
            new_stem = f"{stem}-{counter}"
            if is_directory:
                candidate = workspace / new_stem
            else:
                candidate = workspace / f"{new_stem}{extension}"
            if not candidate.exists():
                return new_stem
            counter += 1
