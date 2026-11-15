"""The assistant's voice: speech to text with Whisper, and text to speech with neural voices.

POST /api/assistant/listen?language=ta  body: the recorded audio (webm, ogg, mp4 or wav)
POST /api/assistant/speak               {"text", "language"} -> audio/mpeg
GET  /api/assistant/voice               which of the two this server can do

Whisper (faster-whisper, model WHISPER_MODEL, "medium" by default) runs on this machine and is
told the language picked in the chat, so Tamil, Malay or Chinese is not heard as English.
Speech comes from Microsoft's neural voices through edge-tts (needs internet), with Singapore
voices for English and Tamil. Both are in the `voice` dependency group; without it, or with no
route to the voice service, the chat falls back to the browser's own speech. Audio is not kept.
"""

from __future__ import annotations

import io
import logging
import os
import threading
from functools import lru_cache

from fastapi import APIRouter, HTTPException, Request, status
from fastapi.responses import Response
from pydantic import BaseModel, Field

log = logging.getLogger(__name__)
router = APIRouter(prefix="/api/assistant")

LANGUAGES = ("en", "zh", "ms", "ta")
VOICES = {
    "en": "en-SG-LunaNeural",
    "zh": "zh-CN-XiaoxiaoNeural",
    "ms": "ms-MY-YasminNeural",
    "ta": "ta-SG-VenbaNeural",
}
MAX_AUDIO_BYTES = 10 * 1024 * 1024
WHISPER_RATE = 16000
MAX_SPEAK_CHARS = 1500
_whisper_lock = threading.Lock()


def whisper_installed() -> bool:
    try:
        import faster_whisper  # noqa: F401
    except ImportError:
        return False
    return True


def speech_installed() -> bool:
    try:
        import edge_tts  # noqa: F401
    except ImportError:
        return False
    return True


@lru_cache(maxsize=1)
def whisper_model():
    """Loaded once; the first call downloads the model (about 1.5 GB for "medium")."""
    from faster_whisper import WhisperModel

    return WhisperModel(os.environ.get("WHISPER_MODEL", "medium"), device="cpu",
                        compute_type="int8")


def samples(audio: bytes):
    """Mono 16 kHz float samples from any recording PyAV can open.

    faster-whisper's own decoder passes an argument PyAV 15 and later removed, so the audio is
    decoded here and handed over as samples.
    """
    import av
    import numpy as np

    resampler = av.AudioResampler(format="s16", layout="mono", rate=WHISPER_RATE)
    chunks = []
    with av.open(io.BytesIO(audio), mode="r") as container:
        for frame in container.decode(audio=0):
            for out in resampler.resample(frame):
                chunks.append(out.to_ndarray().reshape(-1))
        for out in resampler.resample(None):
            chunks.append(out.to_ndarray().reshape(-1))
    if not chunks:
        return np.zeros(0, dtype=np.float32)
    return np.concatenate(chunks).astype(np.float32) / 32768.0


def known_language(language: str) -> str:
    if language not in LANGUAGES:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT,
                            f"language must be one of {', '.join(LANGUAGES)}")
    return language


@router.get("/voice")
def voice_status() -> dict:
    return {"listen": whisper_installed(), "speak": speech_installed(), "languages": LANGUAGES}


@router.post("/listen")
async def listen(request: Request, language: str = "en") -> dict:
    """The words in a short recording, in the language the person picked."""
    known_language(language)
    if not whisper_installed():
        raise HTTPException(status.HTTP_503_SERVICE_UNAVAILABLE, "Speech to text is not installed")
    audio = await request.body()
    if not audio:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, "No audio was sent")
    if len(audio) > MAX_AUDIO_BYTES:
        raise HTTPException(status.HTTP_413_CONTENT_TOO_LARGE, "Keep a recording under 10 MB")
    try:
        sound = samples(audio)
    except Exception as error:  # PyAV raises its own error types for unreadable audio
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT,
                            "That recording could not be read") from error
    with _whisper_lock:  # one transcription at a time keeps a laptop responsive
        segments, _info = whisper_model().transcribe(
            sound, language=language, vad_filter=True, beam_size=1
        )
        text = " ".join(segment.text.strip() for segment in segments).strip()
    return {"text": text, "language": language}


class SpeakRequest(BaseModel):
    text: str = Field(min_length=1, max_length=MAX_SPEAK_CHARS)
    language: str = "en"


@router.post("/speak")
async def speak(body: SpeakRequest) -> Response:
    """A reply read aloud by a neural voice in the chat's language, as MP3."""
    known_language(body.language)
    if not speech_installed():
        raise HTTPException(status.HTTP_503_SERVICE_UNAVAILABLE, "Text to speech is not installed")
    import edge_tts

    audio = bytearray()
    try:
        async for chunk in edge_tts.Communicate(body.text, VOICES[body.language]).stream():
            if chunk["type"] == "audio":
                audio.extend(chunk["data"])
    except Exception as error:  # the voice service is remote; the chat falls back to the browser
        log.warning("Text to speech failed: %s", type(error).__name__)
        raise HTTPException(status.HTTP_502_BAD_GATEWAY, "The voice service did not answer") from error
    return Response(bytes(audio), media_type="audio/mpeg")
