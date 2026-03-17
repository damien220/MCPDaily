"""Unit tests for the naming rules engine."""

import tempfile
from pathlib import Path

import pytest

from LocalFileHandler.naming.categories import CategoryMap
from LocalFileHandler.naming.formatter import NameFormatter
from LocalFileHandler.naming.rules import (
    DatePrefixRule,
    DuplicateRule,
    ExtensionNormalizeRule,
    KebabCaseRule,
    SanitizeRule,
)


# --- Individual Rules ---


class TestSanitizeRule:
    def setup_method(self):
        self.rule = SanitizeRule()
        self.ctx = {}

    def test_strips_special_chars(self):
        assert self.rule.apply('file<>:name', self.ctx) == "filename"

    def test_replaces_brackets(self):
        assert self.rule.apply("report (v2) [final]", self.ctx) == "report-v2-final"

    def test_collapses_whitespace(self):
        assert self.rule.apply("hello   world", self.ctx) == "hello-world"

    def test_strips_leading_trailing_hyphens(self):
        assert self.rule.apply("  -hello- ", self.ctx) == "hello"

    def test_empty_string(self):
        assert self.rule.apply("", self.ctx) == ""


class TestKebabCaseRule:
    def setup_method(self):
        self.rule = KebabCaseRule()
        self.ctx = {}

    def test_spaces_to_hyphens(self):
        assert self.rule.apply("My Report Final", self.ctx) == "my-report-final"

    def test_camel_case(self):
        assert self.rule.apply("camelCaseText", self.ctx) == "camel-case-text"

    def test_underscores(self):
        assert self.rule.apply("snake_case_name", self.ctx) == "snake-case-name"

    def test_already_kebab(self):
        assert self.rule.apply("already-kebab", self.ctx) == "already-kebab"

    def test_mixed(self):
        assert self.rule.apply("My_Complex Name", self.ctx) == "my-complex-name"


class TestDatePrefixRule:
    def setup_method(self):
        self.rule = DatePrefixRule()

    def test_adds_date_prefix(self):
        ctx = {"date_format": "%Y-%m-%d"}
        result = self.rule.apply("report", ctx)
        # Should start with a date pattern YYYY-MM-DD_
        assert result.endswith("_report")
        parts = result.split("_", 1)
        assert len(parts[0].split("-")) == 3  # YYYY-MM-DD

    def test_no_double_prefix(self):
        from datetime import datetime

        today = datetime.now().strftime("%Y-%m-%d")
        ctx = {"date_format": "%Y-%m-%d"}
        result = self.rule.apply(f"{today}_report", ctx)
        assert result == f"{today}_report"

    def test_custom_format(self):
        ctx = {"date_format": "%Y%m%d"}
        result = self.rule.apply("notes", ctx)
        assert "_notes" in result


class TestExtensionNormalizeRule:
    def setup_method(self):
        self.rule = ExtensionNormalizeRule()

    def test_normalizes_jpeg(self):
        cm = CategoryMap()
        ctx = {"extension": ".JPEG", "category_map": cm}
        self.rule.apply("photo", ctx)
        assert ctx["extension"] == ".jpg"

    def test_normalizes_htm(self):
        cm = CategoryMap()
        ctx = {"extension": ".HTM", "category_map": cm}
        self.rule.apply("page", ctx)
        assert ctx["extension"] == ".html"

    def test_keeps_standard(self):
        cm = CategoryMap()
        ctx = {"extension": ".png", "category_map": cm}
        self.rule.apply("image", ctx)
        assert ctx["extension"] == ".png"


class TestDuplicateRule:
    def setup_method(self):
        self.rule = DuplicateRule()

    def test_no_duplicate(self):
        with tempfile.TemporaryDirectory() as tmp:
            ctx = {"target_dir": Path(tmp), "extension": ".txt", "is_directory": False}
            assert self.rule.apply("report", ctx) == "report"

    def test_increments_on_duplicate(self):
        with tempfile.TemporaryDirectory() as tmp:
            (Path(tmp) / "report.txt").touch()
            ctx = {"target_dir": Path(tmp), "extension": ".txt", "is_directory": False}
            assert self.rule.apply("report", ctx) == "report-2"

    def test_increments_multiple(self):
        with tempfile.TemporaryDirectory() as tmp:
            (Path(tmp) / "report.txt").touch()
            (Path(tmp) / "report-2.txt").touch()
            ctx = {"target_dir": Path(tmp), "extension": ".txt", "is_directory": False}
            assert self.rule.apply("report", ctx) == "report-3"

    def test_directory_duplicate(self):
        with tempfile.TemporaryDirectory() as tmp:
            (Path(tmp) / "project").mkdir()
            ctx = {"target_dir": Path(tmp), "extension": "", "is_directory": True}
            assert self.rule.apply("project", ctx) == "project-2"


# --- CategoryMap ---


class TestCategoryMap:
    def setup_method(self):
        self.cm = CategoryMap()

    def test_known_extension(self):
        assert self.cm.get_category(".md") == "documents"
        assert self.cm.get_category(".py") == "code"
        assert self.cm.get_category(".mp4") == "videos"

    def test_unknown_extension(self):
        assert self.cm.get_category(".xyz") is None

    def test_case_insensitive(self):
        assert self.cm.get_category(".MD") == "documents"
        assert self.cm.get_category(".PNG") == "images"

    def test_normalize_extension(self):
        assert self.cm.normalize_extension(".JPEG") == ".jpg"
        assert self.cm.normalize_extension(".png") == ".png"

    def test_add_category(self):
        self.cm.add_category(".custom", "custom_cat")
        assert self.cm.get_category(".custom") == "custom_cat"


# --- NameFormatter ---


class TestNameFormatter:
    def setup_method(self):
        self.tmp = tempfile.mkdtemp()
        self.workspace = Path(self.tmp)
        self.formatter = NameFormatter(
            workspace=self.workspace,
            date_prefix=True,
            auto_categorize=True,
            normalize_extensions=True,
        )

    def test_format_filename_basic(self):
        path, rules = self.formatter.format_filename("Meeting Notes", ".md")
        assert path.exists() is False  # Not created yet
        assert "documents" in str(path)  # auto-categorized
        assert path.suffix == ".md"
        assert "kebab_case" in rules or "sanitize" in rules

    def test_format_filename_extension_normalized(self):
        path, rules = self.formatter.format_filename("photo", ".JPEG")
        assert path.suffix == ".jpg"

    def test_format_dirname(self):
        path, rules = self.formatter.format_dirname("Project Alpha")
        assert "projects" in str(path)
        assert "project-alpha" in str(path)

    def test_format_rename(self):
        stem, ext, rules = self.formatter.format_rename("New Report Name", ".txt")
        assert stem == "new-report-name"
        assert ext == ".txt"

    def test_duplicate_handling(self):
        # Create the category directory and a file
        docs = self.workspace / "documents"
        docs.mkdir(parents=True)
        # First file
        path1, _ = self.formatter.format_filename("report", ".txt")
        path1.parent.mkdir(parents=True, exist_ok=True)
        path1.write_text("first")
        # Second file with same name should get -2
        path2, rules = self.formatter.format_filename("report", ".txt")
        assert "-2" in path2.stem or path2 != path1
