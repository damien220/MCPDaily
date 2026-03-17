"""Unified AI client supporting Anthropic, Ollama, and llama.cpp backends.

Usage
-----
    from LocalFileHandler.ai import create_client
    from LocalFileHandler.config import load_config

    config = load_config()
    client = create_client(config.ai)   # auto-detects the right backend

    if client.available:
        text = client.ask("Summarise this file content", system="You are a file manager.")
        data = client.ask_json("Return JSON only: {category: str, tags: [str]}", ...)

All methods return ``None`` (or empty dict) when the backend is unavailable so
every caller can degrade gracefully without extra try/except logic.
"""

from __future__ import annotations

import json
import logging
from abc import ABC, abstractmethod
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from ..config import AIConfig

log = logging.getLogger(__name__)

# ── Shared helper ─────────────────────────────────────────────────────────────

def _strip_json_fence(text: str) -> str:
    """Remove ```json … ``` fences that LLMs often add around JSON output."""
    text = text.strip()
    if text.startswith("```"):
        lines = text.splitlines()
        # Drop first line (```json or ```) and last line (```)
        inner = lines[1:] if len(lines) > 1 else lines
        if inner and inner[-1].strip() == "```":
            inner = inner[:-1]
        text = "\n".join(inner).strip()
    return text


# ── Abstract base ─────────────────────────────────────────────────────────────

class AIClient(ABC):
    """Common interface for all LLM backends."""

    @property
    @abstractmethod
    def available(self) -> bool:
        """True when the backend is reachable and a model is configured."""

    @property
    @abstractmethod
    def backend_name(self) -> str:
        """Human-readable name of the backend, e.g. ``'anthropic'``."""

    @property
    @abstractmethod
    def model(self) -> str:
        """The model identifier being used."""

    @abstractmethod
    def ask(self, prompt: str, *, system: str = "", max_tokens: int = 512) -> str | None:
        """Send *prompt* to the LLM and return the response text.

        Returns ``None`` if the backend is unavailable or an error occurs.
        """

    def ask_json(
        self,
        prompt: str,
        *,
        system: str = "",
        max_tokens: int = 512,
    ) -> dict | None:
        """Like :meth:`ask` but parses the response as JSON.

        Returns ``None`` on failure; never raises.
        """
        text = self.ask(prompt, system=system, max_tokens=max_tokens)
        if text is None:
            return None
        try:
            return json.loads(_strip_json_fence(text))
        except json.JSONDecodeError as exc:
            log.debug("ask_json parse error: %s — raw: %r", exc, text[:200])
            return None


# ── No-op backend (always returns None) ──────────────────────────────────────

class _NoOpClient(AIClient):
    @property
    def available(self) -> bool:
        return False

    @property
    def backend_name(self) -> str:
        return "none"

    @property
    def model(self) -> str:
        return ""

    def ask(self, prompt: str, *, system: str = "", max_tokens: int = 512) -> None:
        return None


# ── Anthropic (Claude) backend ────────────────────────────────────────────────

class _AnthropicClient(AIClient):
    """Calls the Claude API via the ``anthropic`` SDK."""

    def __init__(self, api_key: str, model: str, max_tokens: int) -> None:
        self._model = model
        self._max_tokens = max_tokens
        self._client = None
        try:
            from anthropic import Anthropic
            self._client = Anthropic(api_key=api_key)
        except ImportError:
            log.warning("anthropic package not installed — AI features disabled")
        except Exception as exc:
            log.warning("Could not initialise Anthropic client: %s", exc)

    @property
    def available(self) -> bool:
        return self._client is not None

    @property
    def backend_name(self) -> str:
        return "anthropic"

    @property
    def model(self) -> str:
        return self._model

    def ask(self, prompt: str, *, system: str = "", max_tokens: int = 512) -> str | None:
        if not self._client:
            return None
        try:
            resp = self._client.messages.create(
                model=self._model,
                max_tokens=max_tokens or self._max_tokens,
                system=system or "You are a helpful file management assistant.",
                messages=[{"role": "user", "content": prompt}],
            )
            return resp.content[0].text
        except Exception as exc:
            log.warning("Anthropic API error: %s", exc)
            return None


# ── Ollama backend ────────────────────────────────────────────────────────────

class _OllamaClient(AIClient):
    """Calls a local Ollama server (http://localhost:11434 by default)."""

    def __init__(self, base_url: str, model: str, max_tokens: int) -> None:
        self._base_url = base_url.rstrip("/")
        self._model = model
        self._max_tokens = max_tokens
        self._ok = self._probe()

    def _probe(self) -> bool:
        """Return True if the Ollama server is reachable."""
        try:
            import requests
            r = requests.get(f"{self._base_url}/api/tags", timeout=3)
            return r.status_code == 200
        except Exception:
            return False

    @property
    def available(self) -> bool:
        return self._ok

    @property
    def backend_name(self) -> str:
        return "ollama"

    @property
    def model(self) -> str:
        return self._model

    def ask(self, prompt: str, *, system: str = "", max_tokens: int = 512) -> str | None:
        if not self._ok:
            return None
        try:
            import requests
            messages = []
            if system:
                messages.append({"role": "system", "content": system})
            messages.append({"role": "user", "content": prompt})
            r = requests.post(
                f"{self._base_url}/api/chat",
                json={"model": self._model, "messages": messages, "stream": False,
                      "options": {"num_predict": max_tokens or self._max_tokens}},
                timeout=120,
            )
            r.raise_for_status()
            return r.json()["message"]["content"]
        except Exception as exc:
            log.warning("Ollama error: %s", exc)
            return None


# ── llama.cpp backend (OpenAI-compatible endpoint) ────────────────────────────

class _LlamaCppClient(AIClient):
    """Calls a llama.cpp server's OpenAI-compatible ``/v1/chat/completions`` endpoint."""

    def __init__(self, base_url: str, model: str, max_tokens: int) -> None:
        self._base_url = base_url.rstrip("/")
        self._model = model or "local"
        self._max_tokens = max_tokens
        self._ok = self._probe()

    def _probe(self) -> bool:
        """Return True if the llama.cpp server is reachable."""
        try:
            import requests
            r = requests.get(f"{self._base_url}/health", timeout=3)
            return r.status_code in (200, 404)   # 404 = server up, no /health route
        except Exception:
            return False

    @property
    def available(self) -> bool:
        return self._ok

    @property
    def backend_name(self) -> str:
        return "llamacpp"

    @property
    def model(self) -> str:
        return self._model

    def ask(self, prompt: str, *, system: str = "", max_tokens: int = 512) -> str | None:
        if not self._ok:
            return None
        try:
            import requests
            messages = []
            if system:
                messages.append({"role": "system", "content": system})
            messages.append({"role": "user", "content": prompt})
            r = requests.post(
                f"{self._base_url}/v1/chat/completions",
                json={"model": self._model, "messages": messages,
                      "max_tokens": max_tokens or self._max_tokens, "stream": False},
                timeout=300,
            )
            r.raise_for_status()
            return r.json()["choices"][0]["message"]["content"]
        except Exception as exc:
            log.warning("llama.cpp error: %s", exc)
            return None


# ── Factory ───────────────────────────────────────────────────────────────────

def create_client(ai_config: "AIConfig") -> AIClient:
    """Instantiate the correct :class:`AIClient` from *ai_config*.

    If ``backend`` is ``"none"`` or the configured backend is unavailable, a
    :class:`_NoOpClient` is returned so callers never need to handle ``None``
    clients.
    """
    backend = (ai_config.backend or "none").lower()

    if backend == "anthropic":
        client: AIClient = _AnthropicClient(
            api_key=ai_config.api_key,
            model=ai_config.model or "claude-haiku-4-5-20251001",
            max_tokens=ai_config.max_tokens,
        )

    elif backend == "ollama":
        client = _OllamaClient(
            base_url=ai_config.base_url or "http://localhost:11434",
            model=ai_config.model or "llama3.2",
            max_tokens=ai_config.max_tokens,
        )

    elif backend == "llamacpp":
        client = _LlamaCppClient(
            base_url=ai_config.base_url or "http://localhost:8080",
            model=ai_config.model or "local",
            max_tokens=ai_config.max_tokens,
        )

    else:
        # backend == "none" or unknown
        return _NoOpClient()

    if not client.available:
        log.info(
            "AI backend '%s' is not reachable — AI features will be disabled.", backend
        )
        return _NoOpClient()

    log.info("AI backend '%s' ready (model: %s)", client.backend_name, client.model)
    return client
