"""
ElevenLabs TTS - converts Diego's dialogue to speech with emotion-driven voice settings.
~10,000 free characters ≈ 100 turns. Toggle with TTS_ENABLED env var.
"""
import os
from collections.abc import AsyncIterator

from elevenlabs import VoiceSettings
from elevenlabs.client import AsyncElevenLabs

from models import Emotion

TTS_ENABLED = os.getenv("TTS_ENABLED", "false").lower() in ("true", "1", "yes")
VOICE_ID = os.getenv("ELEVENLABS_VOICE_ID", "JBFqnCBsd6RMkjVDRZzb")

# Voice settings per emotion - pushed apart for noticeable contrast
# stability: lower = more pitch/speed variation (shaky voice)
# similarity_boost: how close to the original voice (lower = more distorted)
VOICE_SETTINGS = {
    Emotion.CALM:      {"stability": 0.85, "similarity_boost": 0.80},
    Emotion.NERVOUS:   {"stability": 0.40, "similarity_boost": 0.70},
    Emotion.DEFENSIVE: {"stability": 0.55, "similarity_boost": 0.85},
    Emotion.BREAKING:  {"stability": 0.15, "similarity_boost": 0.60},
}

_client: AsyncElevenLabs | None = None


def _get_client() -> AsyncElevenLabs:
    global _client
    if _client is None:
        _client = AsyncElevenLabs(api_key=os.getenv("ELEVENLABS_API_KEY"))
    return _client


async def synthesize_stream(text: str, emotion: Emotion) -> AsyncIterator[bytes]:
    """Yield mp3 chunks as they arrive from ElevenLabs.
    Caller can forward each chunk to the frontend immediately."""
    if not TTS_ENABLED:
        return

    settings = VOICE_SETTINGS[emotion]
    client = _get_client()

    async for chunk in client.text_to_speech.convert(
        voice_id=VOICE_ID,
        text=text,
        voice_settings=VoiceSettings(
            stability=settings["stability"],
            similarity_boost=settings["similarity_boost"],
            style=0.0,
            use_speaker_boost=True,
        ),
        output_format="mp3_22050_32",
        model_id="eleven_flash_v2_5",
    ):
        yield chunk


async def synthesize(text: str, emotion: Emotion) -> bytes | None:
    """Convenience wrapper that collects all chunks into a single buffer."""
    if not TTS_ENABLED:
        return None

    chunks: list[bytes] = []
    async for chunk in synthesize_stream(text, emotion):
        chunks.append(chunk)

    return b"".join(chunks) if chunks else None
