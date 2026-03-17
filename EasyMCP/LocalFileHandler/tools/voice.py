"""VoiceTool — Speech-to-Text tool for LocalFileHandler.

Accepts a base64-encoded audio payload from the browser (WAV or raw PCM),
transcribes it with the configured STT backend, strips the optional wake
word, and returns the transcript.

The web UI then feeds the transcript into the NLCommand panel automatically.

Payload
-------
{
  "audio":       "<base64-encoded WAV bytes>",   # required
  "sample_rate": 16000,                           # optional, default 16000
  "strip_wake_word": true                         # optional, default true
}

Result
------
{
  "transcript":  "create a notes file for today",
  "raw":         "hey filebot create a notes file for today",
  "backend":     "faster_whisper/base",
  "wake_word_detected": true
}
"""

from __future__ import annotations

import base64
import logging
from typing import TYPE_CHECKING

from core.models import MCPRequest, MCPResponse
from core.tool_base import BaseTool

if TYPE_CHECKING:
    from LocalFileHandler.stt.client import STTClient

log = logging.getLogger(__name__)


class VoiceTool(BaseTool):
    """Transcribe audio to text using the configured offline STT backend."""

    name = "voicetool"
    description = (
        "Transcribe a base64-encoded audio clip to text. "
        "Returns the transcript ready for the NL command pipeline."
    )

    def __init__(self, stt_client: "STTClient", wake_word: str = "hey filebot") -> None:
        self._client = stt_client
        self._wake_word = wake_word.lower().strip()

    def handle(self, request: MCPRequest) -> MCPResponse:
        payload = request.payload or {}

        # ── Validate ──────────────────────────────────────────────────────────
        if not self._client.available:
            return MCPResponse.failure(request,
                "STT backend is not configured. "
                "Set STT_BACKEND=faster_whisper (or whisper / vosk / whisper_cpp) "
                "and install the matching package."
            )

        audio_b64 = payload.get("audio")
        if not audio_b64:
            return MCPResponse.failure(request,"Missing required field: 'audio' (base64 WAV).")

        try:
            audio_bytes = base64.b64decode(audio_b64)
        except Exception:
            return MCPResponse.failure(request,"'audio' field is not valid base64.")

        sample_rate: int = int(payload.get("sample_rate", 16000))
        strip_wake = payload.get("strip_wake_word", True)

        # ── Transcribe ────────────────────────────────────────────────────────
        raw = self._client.transcribe(audio_bytes, sample_rate=sample_rate)

        if raw is None:
            return MCPResponse.failure(request,"STT transcription returned no result.")

        raw = raw.strip()
        if not raw:
            return MCPResponse.success(request, {"transcript": "", "raw": "", "backend": self._client.backend_name, "wake_word_detected": False})

        # ── Wake-word gate ────────────────────────────────────────────────────
        wake_detected = False
        transcript = raw

        if self._wake_word and strip_wake:
            lower = raw.lower()
            if lower.startswith(self._wake_word):
                transcript = raw[len(self._wake_word):].lstrip(" ,.")
                wake_detected = True
            # also check if wake word appears anywhere near start (within first 3 words)
            elif self._wake_word in lower[:len(self._wake_word) + 10]:
                idx = lower.find(self._wake_word)
                transcript = raw[idx + len(self._wake_word):].lstrip(" ,.")
                wake_detected = True

        return MCPResponse.success(request, {
            "transcript": transcript,
            "raw": raw,
            "backend": self._client.backend_name,
            "wake_word_detected": wake_detected,
        })
