"""Unified offline Speech-to-Text client.

Backends
--------
whisper        openai-whisper      pip install openai-whisper
faster_whisper faster-whisper      pip install faster-whisper   ← recommended
vosk           Vosk                pip install vosk             ← lightest / Pi
whisper_cpp    whisper.cpp server  external process, OpenAI-compatible HTTP
none           disabled            graceful no-op

All backends expose a single method::

    client.transcribe(audio_bytes, sample_rate=16000) -> str | None
"""

from __future__ import annotations

import base64
import io
import logging
import struct
import wave
from abc import ABC, abstractmethod
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from LocalFileHandler.config import SpeechConfig

log = logging.getLogger(__name__)


# ── Helpers ───────────────────────────────────────────────────────────────────

def _pcm_to_wav(pcm_bytes: bytes, sample_rate: int = 16000,
                channels: int = 1, sampwidth: int = 2) -> bytes:
    """Wrap raw PCM bytes in a WAV container (in-memory)."""
    buf = io.BytesIO()
    with wave.open(buf, "wb") as wf:
        wf.setnchannels(channels)
        wf.setsampwidth(sampwidth)
        wf.setframerate(sample_rate)
        wf.writeframes(pcm_bytes)
    return buf.getvalue()


def _is_wav(data: bytes) -> bool:
    return data[:4] == b"RIFF" and data[8:12] == b"WAVE"


# ── Abstract base ─────────────────────────────────────────────────────────────

class STTClient(ABC):
    """Abstract Speech-to-Text client."""

    @property
    @abstractmethod
    def available(self) -> bool:
        """True if the backend is ready to transcribe."""

    @property
    @abstractmethod
    def backend_name(self) -> str:
        """Human-readable backend identifier."""

    @abstractmethod
    def transcribe(self, audio_bytes: bytes, sample_rate: int = 16000) -> str | None:
        """Transcribe *audio_bytes* (WAV or raw PCM) and return the transcript.

        Returns ``None`` if transcription failed or backend is unavailable.
        """


# ── No-op client ──────────────────────────────────────────────────────────────

class _NoOpSTTClient(STTClient):
    @property
    def available(self) -> bool:
        return False

    @property
    def backend_name(self) -> str:
        return "none"

    def transcribe(self, audio_bytes: bytes, sample_rate: int = 16000) -> str | None:
        return None


# ── openai-whisper ────────────────────────────────────────────────────────────

class _WhisperClient(STTClient):
    """Uses the original openai-whisper library (runs locally, no internet)."""

    def __init__(self, model: str = "base", device: str = "cpu",
                 language: str = "en") -> None:
        self._model_name = model
        self._device = device
        self._language = language or None
        self._model = None
        self._ok = False
        try:
            import whisper  # noqa: PLC0415
            self._model = whisper.load_model(model, device=device)
            self._ok = True
            log.info("openai-whisper loaded model=%s device=%s", model, device)
        except Exception as exc:
            log.warning("openai-whisper unavailable: %s", exc)

    @property
    def available(self) -> bool:
        return self._ok

    @property
    def backend_name(self) -> str:
        return f"whisper/{self._model_name}"

    def transcribe(self, audio_bytes: bytes, sample_rate: int = 16000) -> str | None:
        if not self._ok:
            return None
        try:
            import tempfile, os  # noqa: PLC0415,E401
            import numpy as np  # noqa: PLC0415

            # whisper expects a file path or numpy float32 array
            if _is_wav(audio_bytes):
                with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as f:
                    f.write(audio_bytes)
                    tmp = f.name
                result = self._model.transcribe(tmp, language=self._language)
                os.unlink(tmp)
            else:
                # raw PCM int16 → float32 normalised
                arr = np.frombuffer(audio_bytes, dtype=np.int16).astype(np.float32) / 32768.0
                result = self._model.transcribe(arr, language=self._language)

            return (result.get("text") or "").strip()
        except Exception as exc:
            log.error("whisper transcribe error: %s", exc)
            return None


# ── faster-whisper ────────────────────────────────────────────────────────────

class _FasterWhisperClient(STTClient):
    """Uses faster-whisper (CTranslate2 backend, ~4× faster than openai-whisper)."""

    def __init__(self, model: str = "base", device: str = "cpu",
                 language: str = "en") -> None:
        self._model_name = model
        self._device = device
        self._language = language or None
        self._model = None
        self._ok = False
        try:
            from faster_whisper import WhisperModel  # noqa: PLC0415
            compute = "float32" if device == "cpu" else "float16"
            self._model = WhisperModel(model, device=device, compute_type=compute)
            self._ok = True
            log.info("faster-whisper loaded model=%s device=%s", model, device)
        except Exception as exc:
            log.warning("faster-whisper unavailable: %s", exc)

    @property
    def available(self) -> bool:
        return self._ok

    @property
    def backend_name(self) -> str:
        return f"faster_whisper/{self._model_name}"

    def transcribe(self, audio_bytes: bytes, sample_rate: int = 16000) -> str | None:
        if not self._ok:
            return None
        try:
            import tempfile, os  # noqa: PLC0415,E401

            if not _is_wav(audio_bytes):
                audio_bytes = _pcm_to_wav(audio_bytes, sample_rate)

            with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as f:
                f.write(audio_bytes)
                tmp = f.name

            segments, _ = self._model.transcribe(
                tmp, language=self._language, beam_size=5
            )
            text = " ".join(s.text for s in segments).strip()
            os.unlink(tmp)
            return text
        except Exception as exc:
            log.error("faster-whisper transcribe error: %s", exc)
            return None


# ── Vosk ──────────────────────────────────────────────────────────────────────

class _VoskClient(STTClient):
    """Uses Vosk (very lightweight, excellent for Raspberry Pi / edge devices).

    *model* should be a path to a downloaded Vosk model directory, e.g.
    ``/opt/vosk/vosk-model-small-en-us-0.15``.
    Download from: https://alphacephei.com/vosk/models
    """

    def __init__(self, model: str, language: str = "en") -> None:
        self._model_path = model
        self._language = language
        self._recognizer = None
        self._ok = False
        try:
            from vosk import Model, KaldiRecognizer  # noqa: PLC0415
            import json  # noqa: PLC0415
            self._json = json
            vmodel = Model(model)
            self._recognizer_cls = KaldiRecognizer
            self._vmodel = vmodel
            self._ok = True
            log.info("vosk loaded model=%s", model)
        except Exception as exc:
            log.warning("vosk unavailable: %s", exc)

    @property
    def available(self) -> bool:
        return self._ok

    @property
    def backend_name(self) -> str:
        return "vosk"

    def transcribe(self, audio_bytes: bytes, sample_rate: int = 16000) -> str | None:
        if not self._ok:
            return None
        try:
            # Vosk needs raw PCM int16
            if _is_wav(audio_bytes):
                with io.BytesIO(audio_bytes) as buf:
                    with wave.open(buf) as wf:
                        sample_rate = wf.getframerate()
                        audio_bytes = wf.readframes(wf.getnframes())

            rec = self._recognizer_cls(self._vmodel, sample_rate)
            rec.AcceptWaveform(audio_bytes)
            result = self._json.loads(rec.FinalResult())
            return (result.get("text") or "").strip()
        except Exception as exc:
            log.error("vosk transcribe error: %s", exc)
            return None


# ── whisper.cpp HTTP server ───────────────────────────────────────────────────

class _WhisperCppClient(STTClient):
    """Calls a running whisper.cpp server (OpenAI-compatible /inference endpoint).

    Start the server:
        ./server -m models/ggml-base.bin -l en --host 0.0.0.0 --port 8085
    """

    def __init__(self, base_url: str = "http://localhost:8085",
                 language: str = "en") -> None:
        self._base_url = base_url.rstrip("/")
        self._language = language
        self._ok = self._probe()

    def _probe(self) -> bool:
        try:
            import requests  # noqa: PLC0415
            r = requests.get(f"{self._base_url}/", timeout=3)
            return r.status_code < 500
        except Exception:
            return False

    @property
    def available(self) -> bool:
        return self._ok

    @property
    def backend_name(self) -> str:
        return "whisper_cpp"

    def transcribe(self, audio_bytes: bytes, sample_rate: int = 16000) -> str | None:
        if not self._ok:
            return None
        try:
            import requests  # noqa: PLC0415

            if not _is_wav(audio_bytes):
                audio_bytes = _pcm_to_wav(audio_bytes, sample_rate)

            files = {"file": ("audio.wav", audio_bytes, "audio/wav")}
            data = {"language": self._language, "response_format": "json"}
            r = requests.post(
                f"{self._base_url}/inference", files=files, data=data, timeout=30
            )
            r.raise_for_status()
            return (r.json().get("text") or "").strip()
        except Exception as exc:
            log.error("whisper_cpp transcribe error: %s", exc)
            return None


# ── Factory ───────────────────────────────────────────────────────────────────

def create_stt_client(speech_config: "SpeechConfig") -> STTClient:
    """Instantiate the STT client described by *speech_config*.

    Falls back to ``_NoOpSTTClient`` if the backend library is missing or
    the server is unreachable — the caller never needs to handle ``None``.
    """
    backend = (speech_config.backend or "none").lower()

    if backend == "whisper":
        client: STTClient = _WhisperClient(
            model=speech_config.model,
            device=speech_config.device,
            language=speech_config.language,
        )
    elif backend == "faster_whisper":
        client = _FasterWhisperClient(
            model=speech_config.model,
            device=speech_config.device,
            language=speech_config.language,
        )
    elif backend == "vosk":
        client = _VoskClient(
            model=speech_config.model,
            language=speech_config.language,
        )
    elif backend == "whisper_cpp":
        client = _WhisperCppClient(
            base_url=speech_config.base_url,
            language=speech_config.language,
        )
    else:
        return _NoOpSTTClient()

    if not client.available:
        log.warning("STT backend %r not available; falling back to no-op", backend)
        return _NoOpSTTClient()

    return client
