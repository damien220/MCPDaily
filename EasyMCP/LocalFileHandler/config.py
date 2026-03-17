"""Configuration management for LocalFileHandler."""

import os
from dataclasses import dataclass, field
from pathlib import Path

from dotenv import load_dotenv

# Project root directory (where this file lives)
_PROJECT_DIR = Path(__file__).resolve().parent


@dataclass
class NamingConfig:
    """Configuration for the naming rules engine."""

    date_format: str = "%Y-%m-%d"
    case_style: str = "kebab"  # kebab, snake, camel, pascal
    auto_categorize: bool = True
    date_prefix: bool = True
    normalize_extensions: bool = True
    handle_duplicates: str = "increment"  # increment, timestamp, error


@dataclass
class SpeechConfig:
    """Configuration for offline Speech-to-Text backends.

    Supported backends (set ``STT_BACKEND``):
    - ``whisper``        — openai-whisper        (pip install openai-whisper)
    - ``faster_whisper`` — faster-whisper        (pip install faster-whisper)  ← recommended
    - ``vosk``           — Vosk                  (pip install vosk)             ← lightest/Pi
    - ``whisper_cpp``    — whisper.cpp HTTP       (OpenAI-compatible server)
    - ``none``           — STT disabled

    Whisper / faster-whisper model sizes:
      tiny (39MB) · base (74MB) · small (244MB) · medium (769MB)
      large-v3-turbo (809MB, best quality/speed) · large-v3 (1.5GB, max accuracy)

    Recommended faster-whisper HuggingFace repos:
      Systran/faster-whisper-base
      Systran/faster-whisper-large-v3-turbo   ← recommended

    Vosk models (ultra-light, great for Raspberry Pi):
      vosk-model-small-en-us-0.15  (40 MB)
      vosk-model-en-us-0.22        (1.8 GB, high accuracy)
    """

    backend: str = "none"          # whisper | faster_whisper | vosk | whisper_cpp | none
    model: str = "base"            # model name / path (backend-specific)
    language: str = "en"           # ISO-639-1 language code
    device: str = "cpu"            # cpu | cuda | auto
    base_url: str = "http://localhost:8085"   # whisper_cpp server URL
    wake_word: str = "hey filebot"            # empty string to disable


@dataclass
class AIConfig:
    """Configuration for AI/LLM backends.

    Supported backends (set ``AI_BACKEND`` or let the app auto-detect):
    - ``anthropic``  — Claude API (requires ``ANTHROPIC_API_KEY``)
    - ``ollama``     — local Ollama server  (default URL: http://localhost:11434)
    - ``llamacpp``   — llama.cpp server, OpenAI-compatible (default: http://localhost:8080)
    - ``none``       — AI features disabled (graceful degradation)

    Auto-detection order when ``AI_BACKEND`` is not set:
      1. ANTHROPIC_API_KEY present → anthropic
      2. Ollama reachable at OLLAMA_BASE_URL → ollama
      3. llama.cpp reachable at LLAMACPP_BASE_URL → llamacpp
      4. No backend reachable → none (all AI tools return an informative message)
    """

    backend: str = "none"
    api_key: str = ""                            # Anthropic API key
    model: str = ""                              # model name (backend-specific defaults below)
    base_url: str = ""                           # Ollama / llama.cpp server URL
    max_tokens: int = 1024


@dataclass
class Config:
    """Application configuration loaded from environment variables."""

    workspace_path: Path = field(default_factory=lambda: Path("workspace"))
    server_host: str = "127.0.0.1"
    server_port: int = 8080
    trash_enabled: bool = True
    trash_dir: str = ".trash"
    max_file_size_mb: int = 100
    auth_username: str = ""
    auth_password: str = ""
    naming: NamingConfig = field(default_factory=NamingConfig)
    ai: AIConfig = field(default_factory=AIConfig)
    speech: SpeechConfig = field(default_factory=SpeechConfig)


def load_config(env_file: str | None = None) -> Config:
    """Load configuration from environment variables and .env file."""
    if env_file:
        load_dotenv(env_file)
    else:
        load_dotenv()

    naming = NamingConfig(
        date_format=os.getenv("NAMING_DATE_FORMAT", "%Y-%m-%d"),
        case_style=os.getenv("NAMING_CASE_STYLE", "kebab"),
        auto_categorize=os.getenv("NAMING_AUTO_CATEGORIZE", "true").lower() == "true",
        date_prefix=os.getenv("NAMING_DATE_PREFIX", "true").lower() == "true",
        normalize_extensions=os.getenv("NAMING_NORMALIZE_EXTENSIONS", "true").lower()
        == "true",
        handle_duplicates=os.getenv("NAMING_HANDLE_DUPLICATES", "increment"),
    )

    raw_workspace = os.getenv("WORKSPACE_PATH", "workspace")
    workspace = Path(raw_workspace)
    if not workspace.is_absolute():
        workspace = _PROJECT_DIR / workspace

    # ── AI backend ──────────────────────────────────────────────────────────
    api_key  = os.getenv("ANTHROPIC_API_KEY", "")
    backend  = os.getenv("AI_BACKEND", "")   # explicit override

    if not backend:
        # Auto-detect: prefer Anthropic when key is present, then Ollama, then llama.cpp
        if api_key:
            backend = "anthropic"
        else:
            backend = "none"   # Ollama/llama.cpp reachability checked in ai/client.py

    # Default model names per backend
    default_models = {
        "anthropic": "claude-haiku-4-5-20251001",
        "ollama":    "llama3.2",
        "llamacpp":  "local",
    }
    model = os.getenv("AI_MODEL", default_models.get(backend, ""))

    ai = AIConfig(
        backend=backend,
        api_key=api_key,
        model=model,
        base_url=os.getenv(
            "OLLAMA_BASE_URL" if backend == "ollama" else "LLAMACPP_BASE_URL",
            "http://localhost:11434" if backend == "ollama" else "http://localhost:8080",
        ),
        max_tokens=int(os.getenv("AI_MAX_TOKENS", "1024")),
    )

    # ── Speech / STT backend ────────────────────────────────────────────────
    speech = SpeechConfig(
        backend=os.getenv("STT_BACKEND", "none"),
        model=os.getenv("STT_MODEL", "base"),
        language=os.getenv("STT_LANGUAGE", "en"),
        device=os.getenv("STT_DEVICE", "cpu"),
        base_url=os.getenv("STT_BASE_URL", "http://localhost:8085"),
        wake_word=os.getenv("STT_WAKE_WORD", "hey filebot"),
    )

    config = Config(
        workspace_path=workspace,
        server_host=os.getenv("SERVER_HOST", "127.0.0.1"),
        server_port=int(os.getenv("SERVER_PORT", "8080")),
        trash_enabled=os.getenv("TRASH_ENABLED", "true").lower() == "true",
        trash_dir=os.getenv("TRASH_DIR", ".trash"),
        max_file_size_mb=int(os.getenv("MAX_FILE_SIZE_MB", "100")),
        auth_username=os.getenv("AUTH_USERNAME", ""),
        auth_password=os.getenv("AUTH_PASSWORD", ""),
        naming=naming,
        ai=ai,
        speech=speech,
    )

    # Ensure workspace directory exists
    config.workspace_path.mkdir(parents=True, exist_ok=True)

    return config
