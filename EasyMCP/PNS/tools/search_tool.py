"""
SearchTool - Full-text search across notes.

Fields:
- query (required): Search terms to find in notes
- tag (optional): Filter results by tag
- limit (optional): Maximum number of results (default 20)
"""

from pathlib import Path
from typing import Any

from storage.file_storage import FileStorage
from core.tool_base import BaseTool
from core.models import MCPResponse

class SearchTool(BaseTool):
    """Tool for searching notes by content and title."""

    name = "searchtool"
    description = "Full-text search across note content and titles"

    def __init__(self, storage_path: Path):
        """
        Initialize SearchTool.

        Args:
            storage_path: Path to the notes storage directory.
        """
        super().__init__()
        self.storage = FileStorage(storage_path)

    def _make_response(self, request: Any, data: dict[str, Any], success: bool = True) -> MCPResponse:
        """Create an MCPResponse from the request and data."""
        request_id = request.id if hasattr(request, 'id') else "unknown"
        status = "success" if success else "error"
        return MCPResponse(id=request_id, status=status, result=data)

    def handle(self, request: Any) -> MCPResponse:
        """
        Handle a search query.

        Args:
            request: MCPRequest object containing payload with search parameters:
                - query (required): Search terms
                - tag (optional): Filter by tag
                - limit (optional): Max results (default 20)

        Returns:
            MCPResponse object with search results or error.
        """
        # Extract payload from MCPRequest object
        payload = request.payload if hasattr(request, 'payload') else request

        # Validate required field
        query = payload.get("query")

        if not query:
            return self._make_response(request, {
                "success": False,
                "error": "Missing required field: query",
            }, success=False)

        if not isinstance(query, str):
            return self._make_response(request, {
                "success": False,
                "error": "Query must be a string",
            }, success=False)

        query = query.strip()
        if not query:
            return self._make_response(request, {
                "success": False,
                "error": "Query cannot be empty",
            }, success=False)

        # Get optional parameters
        tag = payload.get("tag")
        limit = payload.get("limit", 20)

        # Validate limit
        try:
            limit = int(limit)
            if limit < 1:
                limit = 20
            if limit > 100:
                limit = 100
        except (ValueError, TypeError):
            limit = 20

        try:
            # Perform search
            results = self.storage.search(
                query=query,
                tag=tag,
                limit=limit
            )

            return self._make_response(request, {
                "success": True,
                "query": query,
                "tag": tag,
                "results": results,
                "count": len(results),
                "limit": limit,
            }, success=True)

        except Exception as e:
            return self._make_response(request, {
                "success": False,
                "error": f"Search failed: {str(e)}",
            }, success=False)
