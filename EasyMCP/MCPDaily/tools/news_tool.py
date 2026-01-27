"""News Tool - Provides news headlines from various sources.

This tool extends the mcplearn framework's BaseTool to provide news headlines
using the NewsAPI service or RSS feeds as a fallback.
"""

import time
from typing import Optional, Dict, Any, List
import requests
from datetime import datetime

from core.tool_base import BaseTool
from core.models import MCPRequest, MCPResponse


class NewsTool(BaseTool):
    """Provides news headlines from various sources.

    This tool fetches news headlines from NewsAPI with support for:
    - Filtering by source
    - Filtering by category
    - Limiting number of results
    - Basic in-memory caching

    Categories supported: general, business, entertainment, health,
                          science, sports, technology
    """

    # Valid categories for NewsAPI
    VALID_CATEGORIES = {
        "general", "business", "entertainment", "health",
        "science", "sports", "technology"
    }

    def __init__(
        self,
        api_key: Optional[str] = None,
        api_base_url: str = "https://newsapi.org/v2",
        cache_duration: int = 300,
        default_limit: int = 10,
        **kwargs
    ):
        """Initialize the News Tool.

        Args:
            api_key: NewsAPI API key (optional, will use RSS feeds if not provided).
            api_base_url: Base URL for the news API.
            cache_duration: Cache duration in seconds (default: 300 = 5 minutes).
            default_limit: Default number of headlines to return.
            **kwargs: Additional arguments passed to BaseTool.
        """
        super().__init__(**kwargs)
        self.api_key = api_key
        self.api_base_url = api_base_url
        self.cache_duration = cache_duration
        self.default_limit = default_limit
        self.cache: Dict[str, tuple[float, List[Dict[str, Any]]]] = {}

    def _get_cache_key(self, category: str, source: Optional[str], limit: int) -> str:
        """Generate cache key from parameters.

        Args:
            category: News category.
            source: News source (optional).
            limit: Number of results.

        Returns:
            Cache key string.
        """
        return f"{category}:{source or 'all'}:{limit}"

    def _get_cached_news(self, cache_key: str) -> Optional[List[Dict[str, Any]]]:
        """Get news data from cache if available and not expired.

        Args:
            cache_key: Cache key identifier.

        Returns:
            Cached news data or None if not cached or expired.
        """
        if cache_key in self.cache:
            timestamp, data = self.cache[cache_key]
            if time.time() - timestamp < self.cache_duration:
                return data
            else:
                # Remove expired entry
                del self.cache[cache_key]

        return None

    def _cache_news(self, cache_key: str, data: List[Dict[str, Any]]) -> None:
        """Store news data in cache.

        Args:
            cache_key: Cache key identifier.
            data: News data to cache.
        """
        self.cache[cache_key] = (time.time(), data)

    def _fetch_news_from_api(
        self,
        category: str,
        source: Optional[str],
        limit: int
    ) -> List[Dict[str, Any]]:
        """Fetch news from NewsAPI.

        Args:
            category: News category.
            source: News source (optional).
            limit: Number of headlines to fetch.

        Returns:
            List of parsed news headlines.

        Raises:
            ValueError: If API returns an error.
            requests.RequestException: If API request fails.
        """
        if not self.api_key:
            raise ValueError(
                "News API key not configured. Please set NEWS_API_KEY environment variable."
            )

        # Build API request
        url = f"{self.api_base_url}/top-headlines"
        params = {
            "apiKey": self.api_key,
            "category": category if category != "general" else None,
            "pageSize": min(limit, 100),  # API max is 100
            "language": "en",  # English only for now
        }

        if source:
            params["sources"] = source

        # Remove None values
        params = {k: v for k, v in params.items() if v is not None}

        # Make API request
        response = requests.get(url, params=params, timeout=10)

        if response.status_code == 401:
            raise ValueError("Invalid News API key.")
        elif response.status_code == 426:
            raise ValueError("News API key requires upgrade for this feature.")
        elif response.status_code != 200:
            raise ValueError(f"News API error: {response.status_code}")

        data = response.json()

        if data.get("status") != "ok":
            raise ValueError(f"News API error: {data.get('message', 'Unknown error')}")

        # Parse articles
        articles = data.get("articles", [])
        headlines = []

        for article in articles:
            headlines.append({
                "title": article.get("title", "No title"),
                "description": article.get("description", ""),
                "url": article.get("url", ""),
                "source": article.get("source", {}).get("name", "Unknown"),
                "published_at": article.get("publishedAt", ""),
                "author": article.get("author"),
                "image_url": article.get("urlToImage"),
            })

        return headlines

    def _fetch_news_fallback(
        self,
        category: str,
        limit: int
    ) -> List[Dict[str, Any]]:
        """Fallback method when API key is not available.

        Provides mock/placeholder data for testing or returns a helpful message.

        Args:
            category: News category.
            limit: Number of headlines.

        Returns:
            List of placeholder news items.
        """
        # Return a helpful message when API key is not configured
        return [{
            "title": "News API Configuration Required",
            "description": (
                "To fetch real news headlines, please configure your NEWS_API_KEY "
                "environment variable with a valid API key from newsapi.org"
            ),
            "url": "https://newsapi.org",
            "source": "MCPDaily",
            "published_at": datetime.now().isoformat(),
            "author": None,
            "image_url": None,
        }]

    def validate(self, request: MCPRequest) -> None:
        """Validate the incoming request.

        Args:
            request: The incoming MCP request.

        Raises:
            ValueError: If category is invalid.
        """
        category = request.payload.get("category", "general")

        if category not in self.VALID_CATEGORIES:
            raise ValueError(
                f"Invalid category: '{category}'. "
                f"Valid categories are: {', '.join(sorted(self.VALID_CATEGORIES))}"
            )

    def handle(self, request: MCPRequest) -> MCPResponse:
        """Handle news headlines request.

        Args:
            request: The incoming MCP request with optional filters.

        Returns:
            MCPResponse with news headlines or error.

        Expected payload:
            {
                "category": "technology",  // optional, default: "general"
                "source": "bbc-news",      // optional
                "limit": 10                // optional, default: 10
            }

        Response format:
            {
                "category": "technology",
                "source": "bbc-news",
                "count": 10,
                "headlines": [...]
            }
        """
        try:
            # Extract parameters
            category = request.payload.get("category", "general")
            source = request.payload.get("source")
            limit = request.payload.get("limit", self.default_limit)

            # Ensure limit is an integer
            if isinstance(limit, str):
                limit = int(limit)

            limit = max(1, min(limit, 100))  # Clamp between 1 and 100

            # Generate cache key
            cache_key = self._get_cache_key(category, source, limit)

            # Check cache first
            cached_data = self._get_cached_news(cache_key)
            if cached_data:
                return MCPResponse.success(request, {
                    "category": category,
                    "source": source,
                    "count": len(cached_data),
                    "headlines": cached_data,
                    "cached": True,
                })

            # Fetch news
            try:
                headlines = self._fetch_news_from_api(category, source, limit)
            except (ValueError, requests.RequestException) as e:
                # Use fallback if API fails
                if "API key not configured" in str(e):
                    headlines = self._fetch_news_fallback(category, limit)
                else:
                    raise

            # Cache the result
            self._cache_news(cache_key, headlines)

            return MCPResponse.success(request, {
                "category": category,
                "source": source,
                "count": len(headlines),
                "headlines": headlines,
                "cached": False,
            })

        except requests.RequestException as e:
            return MCPResponse.failure(
                request,
                f"Failed to fetch news data: {str(e)}"
            )
        except Exception as e:
            return MCPResponse.failure(
                request,
                f"News tool error: {str(e)}"
            )
