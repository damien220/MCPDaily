"""
Configuration management for PNS.

Loads configuration from environment variables with support for .env files.
"""

import os
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

from dotenv import load_dotenv


@dataclass
class PNSConfig:
    """Configuration settings for PNS application."""

    host: str
    port: int
    notes_directory: Path

    def validate(self) -> list[str]:
        """Validate configuration and return list of warnings."""
        warnings = []

        if self.port < 1 or self.port > 65535:
            warnings.append(f"Invalid port number: {self.port}. Using default 8081.")

        return warnings


def load_config(env_file: Optional[str] = None) -> PNSConfig:
    """
    Load configuration from environment variables.

    Args:
        env_file: Optional path to .env file. If not provided, searches for .env
                  in the PNS directory.

    Returns:
        PNSConfig instance with loaded configuration.
    """
    # Determine the base directory (PNS project root)
    base_dir = Path(__file__).parent

    # Load .env file if it exists
    if env_file:
        env_path = Path(env_file)
    else:
        env_path = base_dir / ".env"

    if env_path.exists():
        load_dotenv(env_path)
    else:
        # Try to load from parent directory as fallback
        parent_env = base_dir.parent / ".env"
        if parent_env.exists():
            load_dotenv(parent_env)

    # Load configuration values with defaults
    host = os.getenv("PNS_HOST", "127.0.0.1")
    port = int(os.getenv("PNS_PORT", "8081"))

    # Handle notes directory path
    notes_dir_str = os.getenv("NOTES_DIRECTORY", "./notes")
    notes_directory = Path(notes_dir_str)

    # If relative path, make it relative to the PNS directory
    if not notes_directory.is_absolute():
        notes_directory = base_dir / notes_directory

    # Ensure notes directory exists
    notes_directory.mkdir(parents=True, exist_ok=True)

    config = PNSConfig(
        host=host,
        port=port,
        notes_directory=notes_directory.resolve()
    )

    # Validate and print warnings
    warnings = config.validate()
    for warning in warnings:
        print(f"[PNS Config Warning] {warning}")

    return config
