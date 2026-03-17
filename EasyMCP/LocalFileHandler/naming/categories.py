"""File extension to category mapping."""

# Default extension → category mapping
DEFAULT_CATEGORIES: dict[str, str] = {
    # Documents
    ".doc": "documents",
    ".docx": "documents",
    ".pdf": "documents",
    ".txt": "documents",
    ".md": "documents",
    ".odt": "documents",
    ".rtf": "documents",
    # Spreadsheets
    ".xls": "spreadsheets",
    ".xlsx": "spreadsheets",
    ".csv": "spreadsheets",
    ".ods": "spreadsheets",
    # Images
    ".jpg": "images",
    ".jpeg": "images",
    ".png": "images",
    ".gif": "images",
    ".svg": "images",
    ".webp": "images",
    ".bmp": "images",
    ".ico": "images",
    # Videos
    ".mp4": "videos",
    ".avi": "videos",
    ".mkv": "videos",
    ".mov": "videos",
    ".webm": "videos",
    ".wmv": "videos",
    # Audio
    ".mp3": "audio",
    ".wav": "audio",
    ".flac": "audio",
    ".ogg": "audio",
    ".m4a": "audio",
    ".aac": "audio",
    # Code
    ".py": "code",
    ".js": "code",
    ".ts": "code",
    ".java": "code",
    ".c": "code",
    ".cpp": "code",
    ".go": "code",
    ".rs": "code",
    ".html": "code",
    ".css": "code",
    ".sh": "code",
    # Archives
    ".zip": "archives",
    ".tar": "archives",
    ".gz": "archives",
    ".rar": "archives",
    ".7z": "archives",
    ".bz2": "archives",
    # Data
    ".json": "data",
    ".xml": "data",
    ".yaml": "data",
    ".yml": "data",
    ".toml": "data",
    ".ini": "data",
    ".cfg": "data",
}

# Extension normalization mapping (non-standard → standard)
EXTENSION_NORMALIZE: dict[str, str] = {
    ".jpeg": ".jpg",
    ".htm": ".html",
    ".tif": ".tiff",
    ".yml": ".yaml",
}

# Default category for directories
DIR_CATEGORIES: dict[str, str] = {
    "projects": "projects",
}


class CategoryMap:
    """Manages file extension to category mapping."""

    def __init__(
        self,
        categories: dict[str, str] | None = None,
        ext_normalize: dict[str, str] | None = None,
    ):
        self._categories = dict(categories or DEFAULT_CATEGORIES)
        self._ext_normalize = dict(ext_normalize or EXTENSION_NORMALIZE)

    def get_category(self, extension: str) -> str | None:
        """Return the category for a file extension, or None if unmapped."""
        ext = extension.lower()
        # Normalize first, then look up
        ext = self._ext_normalize.get(ext, ext)
        return self._categories.get(ext)

    def normalize_extension(self, extension: str) -> str:
        """Normalize a file extension (e.g. .JPEG → .jpg)."""
        ext = extension.lower()
        return self._ext_normalize.get(ext, ext)

    def add_category(self, extension: str, category: str) -> None:
        """Add or update a category mapping."""
        self._categories[extension.lower()] = category

    def all_categories(self) -> set[str]:
        """Return all unique category names."""
        return set(self._categories.values())
