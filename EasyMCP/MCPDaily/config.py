"""Configuration management for MCPDaily application.

This module provides centralized configuration using environment variables
with sensible defaults for local development.
"""

import os
from pathlib import Path
from dataclasses import dataclass
from typing import Optional

# Load .env file if it exists
try:
    from dotenv import load_dotenv
    # Get the directory where this config.py file is located
    config_dir = Path(__file__).parent
    env_path = config_dir / '.env'
    if env_path.exists():
        load_dotenv(dotenv_path=env_path)
        print(f"[CONFIG] Loaded environment from: {env_path}")
    else:
        print(f"[CONFIG] No .env file found at: {env_path}")
except ImportError:
    print("[CONFIG] python-dotenv not installed, using system environment variables only")
    pass


@dataclass
class MCPDailyConfig:
    """Configuration settings for MCPDaily application."""

    # Server settings
    host: str = os.getenv("MCP_DAILY_HOST", "127.0.0.1")
    port: int = int(os.getenv("MCP_DAILY_PORT", "8080"))

    # API Keys
    weather_api_key: str = os.getenv("WEATHER_API_KEY", "")
    news_api_key: str = os.getenv("NEWS_API_KEY", "")

    # Tool settings
    default_timezone: str = os.getenv("DEFAULT_TIMEZONE", "UTC")
    cache_duration: int = int(os.getenv("CACHE_DURATION", "300"))  # 5 minutes in seconds

    # Weather API settings
    weather_api_base_url: str = os.getenv(
        "WEATHER_API_BASE_URL",
        "https://api.openweathermap.org/data/2.5"
    )

    # News API settings
    news_api_base_url: str = os.getenv(
        "NEWS_API_BASE_URL",
        "https://newsapi.org/v2"
    )

    def validate(self) -> list[str]:
        """Validate configuration and return list of warnings/errors.

        Returns:
            List of warning/error messages. Empty list if configuration is valid.
        """
        issues = []

        if not self.weather_api_key:
            issues.append("WARNING: WEATHER_API_KEY not set. Weather tool may not work.")

        if not self.news_api_key:
            issues.append("WARNING: NEWS_API_KEY not set. News tool may not work.")

        if self.port < 1 or self.port > 65535:
            issues.append(f"ERROR: Invalid port number: {self.port}")

        return issues


def load_config() -> MCPDailyConfig:
    """Load and validate configuration.

    Returns:
        Configured MCPDailyConfig instance.

    Raises:
        ValueError: If configuration has critical errors.
    """
    config = MCPDailyConfig()
    issues = config.validate()

    # Print warnings
    for issue in issues:
        if issue.startswith("WARNING"):
            print(f"[CONFIG] {issue}")
        elif issue.startswith("ERROR"):
            raise ValueError(issue)

    return config
