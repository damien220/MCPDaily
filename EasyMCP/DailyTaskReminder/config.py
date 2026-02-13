"""Configuration for DailyTaskReminder."""

import os
from pathlib import Path


# --- Storage ---
STORAGE_DIR = Path(os.environ.get(
    "DTR_STORAGE_DIR",
    os.path.expanduser("~/.dailytaskreminder"),
))
STORAGE_PATH = STORAGE_DIR / "tasks.json"

# --- Reminder polling ---
POLL_INTERVAL = int(os.environ.get("DTR_POLL_INTERVAL", "60"))  # seconds

# --- Display ---
DEFAULT_TIMEZONE = os.environ.get("DTR_TIMEZONE", "UTC")

# --- App metadata ---
APP_NAME = "DailyTaskReminder"
APP_VERSION = "0.1.0"
