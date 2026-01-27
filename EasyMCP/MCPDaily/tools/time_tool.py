"""Time Tool - Provides current time and timezone information.

This tool extends the mcplearn framework's BaseTool to provide time-related
functionality including timezone conversions and timestamp generation.
"""

from datetime import datetime
from zoneinfo import ZoneInfo, available_timezones
from typing import Optional

from core.tool_base import BaseTool
from core.models import MCPRequest, MCPResponse


class TimeTool(BaseTool):
    """Provides current time and timezone information.

    This tool returns the current time in various formats including:
    - Local time in specified timezone
    - UTC time
    - Unix timestamp
    - Timezone information

    The tool accepts an optional timezone parameter and defaults to UTC if not provided.
    """

    def __init__(self, default_timezone: str = "UTC", **kwargs):
        """Initialize the Time Tool.

        Args:
            default_timezone: Default timezone to use if not specified in request.
            **kwargs: Additional arguments passed to BaseTool.
        """
        super().__init__(**kwargs)
        self.default_timezone = default_timezone

    def validate(self, request: MCPRequest) -> None:
        """Validate the incoming request.

        Args:
            request: The incoming MCP request.

        Raises:
            ValueError: If timezone is invalid.
        """
        timezone = request.payload.get("timezone")

        if timezone and timezone not in available_timezones():
            # Try to provide helpful error message
            raise ValueError(
                f"Invalid timezone: '{timezone}'. "
                f"Please use a valid timezone name (e.g., 'America/New_York', 'Europe/London', 'UTC')."
            )

    def handle(self, request: MCPRequest) -> MCPResponse:
        """Handle time information request.

        Args:
            request: The incoming MCP request with optional 'timezone' in payload.

        Returns:
            MCPResponse with time information or error.

        Expected payload:
            {
                "timezone": "America/New_York"  // optional, defaults to UTC
            }

        Response format:
            {
                "current_time": "2026-01-01 10:30:45",
                "timezone": "America/New_York",
                "timezone_abbr": "EST",
                "utc_time": "2026-01-01 15:30:45",
                "timestamp": 1735742445,
                "iso_format": "2026-01-01T10:30:45-05:00"
            }
        """
        try:
            # Get timezone from payload or use default
            timezone_str = request.payload.get("timezone", self.default_timezone)

            # Get current time
            now_utc = datetime.now(ZoneInfo("UTC"))
            now_local = now_utc.astimezone(ZoneInfo(timezone_str))

            # Format response
            result = {
                "current_time": now_local.strftime("%Y-%m-%d %H:%M:%S"),
                "timezone": timezone_str,
                "timezone_abbr": now_local.strftime("%Z"),
                "utc_time": now_utc.strftime("%Y-%m-%d %H:%M:%S"),
                "timestamp": int(now_utc.timestamp()),
                "iso_format": now_local.isoformat(),
                "utc_offset": now_local.strftime("%z"),
            }

            # Optional: Add day of week and other useful info
            result["day_of_week"] = now_local.strftime("%A")
            result["date"] = now_local.strftime("%Y-%m-%d")
            result["time_12hr"] = now_local.strftime("%I:%M:%S %p")

            return MCPResponse.success(request, result)

        except Exception as e:
            return MCPResponse.failure(
                request,
                f"Failed to get time information: {str(e)}"
            )
