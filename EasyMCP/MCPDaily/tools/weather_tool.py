"""Weather Tool - Provides weather forecast information.

This tool extends the mcplearn framework's BaseTool to provide weather data
using the OpenWeatherMap API with basic caching to minimize API calls.
"""

import time
from typing import Optional, Dict, Any
import requests

from core.tool_base import BaseTool
from core.models import MCPRequest, MCPResponse


class WeatherTool(BaseTool):
    """Provides weather forecast information for specified locations.

    This tool fetches current weather data from OpenWeatherMap API and includes
    basic in-memory caching to reduce API calls. The cache expires after a
    configurable duration (default: 5 minutes).

    Features:
    - Current weather conditions
    - Temperature (with feels-like)
    - Humidity and pressure
    - Wind speed and direction
    - Weather description
    - Sunrise/sunset times
    """

    def __init__(
        self,
        api_key: str,
        api_base_url: str = "https://api.openweathermap.org/data/2.5",
        cache_duration: int = 300,
        **kwargs
    ):
        """Initialize the Weather Tool.

        Args:
            api_key: OpenWeatherMap API key.
            api_base_url: Base URL for the weather API.
            cache_duration: Cache duration in seconds (default: 300 = 5 minutes).
            **kwargs: Additional arguments passed to BaseTool.
        """
        super().__init__(**kwargs)
        self.api_key = api_key
        self.api_base_url = api_base_url
        self.cache_duration = cache_duration
        self.cache: Dict[str, tuple[float, Dict[str, Any]]] = {}

    def _get_cached_weather(self, location: str) -> Optional[Dict[str, Any]]:
        """Get weather data from cache if available and not expired.

        Args:
            location: Location identifier (cache key).

        Returns:
            Cached weather data or None if not cached or expired.
        """
        if location in self.cache:
            timestamp, data = self.cache[location]
            if time.time() - timestamp < self.cache_duration:
                return data
            else:
                # Remove expired entry
                del self.cache[location]

        return None

    def _cache_weather(self, location: str, data: Dict[str, Any]) -> None:
        """Store weather data in cache.

        Args:
            location: Location identifier (cache key).
            data: Weather data to cache.
        """
        self.cache[location] = (time.time(), data)

    def _fetch_weather(self, location: str) -> Dict[str, Any]:
        """Fetch weather data from OpenWeatherMap API.

        Args:
            location: City name or location query.

        Returns:
            Parsed weather data.

        Raises:
            requests.RequestException: If API request fails.
            ValueError: If API returns an error or invalid data.
        """
        if not self.api_key:
            raise ValueError(
                "Weather API key not configured. Please set WEATHER_API_KEY environment variable."
            )

        # Build API request URL
        url = f"{self.api_base_url}/weather"
        params = {
            "q": location,
            "appid": self.api_key,
            "units": "metric",  # Use Celsius
        }

        # Make API request
        response = requests.get(url, params=params, timeout=10)

        if response.status_code == 401:
            raise ValueError("Invalid Weather API key.")
        elif response.status_code == 404:
            raise ValueError(f"Location not found: '{location}'")
        elif response.status_code != 200:
            raise ValueError(f"Weather API error: {response.status_code}")

        data = response.json()

        # Parse and structure the weather data
        return {
            "location": f"{data['name']}, {data['sys']['country']}",
            "coordinates": {
                "lat": data['coord']['lat'],
                "lon": data['coord']['lon']
            },
            "temperature": {
                "current": round(data['main']['temp'], 1),
                "feels_like": round(data['main']['feels_like'], 1),
                "min": round(data['main']['temp_min'], 1),
                "max": round(data['main']['temp_max'], 1),
                "unit": "celsius"
            },
            "conditions": {
                "main": data['weather'][0]['main'],
                "description": data['weather'][0]['description'].capitalize(),
                "icon": data['weather'][0]['icon']
            },
            "humidity": data['main']['humidity'],
            "pressure": data['main']['pressure'],
            "wind": {
                "speed": data['wind']['speed'],
                "direction": data['wind'].get('deg', 0)
            },
            "visibility": data.get('visibility', 0) / 1000,  # Convert to km
            "cloudiness": data['clouds']['all'],
            "timestamp": data['dt'],
            "sunrise": data['sys']['sunrise'],
            "sunset": data['sys']['sunset'],
        }

    def validate(self, request: MCPRequest) -> None:
        """Validate the incoming request.

        Args:
            request: The incoming MCP request.

        Raises:
            ValueError: If location is missing from payload.
        """
        location = request.payload.get("location")

        if not location or not isinstance(location, str) or not location.strip():
            raise ValueError("Payload must include a non-empty 'location' field.")

    def handle(self, request: MCPRequest) -> MCPResponse:
        """Handle weather information request.

        Args:
            request: The incoming MCP request with 'location' in payload.

        Returns:
            MCPResponse with weather information or error.

        Expected payload:
            {
                "location": "New York"
            }

        Response format:
            {
                "location": "New York, US",
                "temperature": {...},
                "conditions": {...},
                "humidity": 65,
                ...
            }
        """
        try:
            location = request.payload.get("location", "").strip()

            # Check cache first
            cached_data = self._get_cached_weather(location.lower())
            if cached_data:
                cached_data["cached"] = True
                return MCPResponse.success(request, cached_data)

            # Fetch from API
            weather_data = self._fetch_weather(location)
            weather_data["cached"] = False

            # Cache the result
            self._cache_weather(location.lower(), weather_data)

            return MCPResponse.success(request, weather_data)

        except requests.RequestException as e:
            return MCPResponse.failure(
                request,
                f"Failed to fetch weather data: {str(e)}"
            )
        except Exception as e:
            return MCPResponse.failure(
                request,
                f"Weather tool error: {str(e)}"
            )
