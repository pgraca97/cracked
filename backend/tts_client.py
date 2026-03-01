"""
ElevenLabs TTS - converts Diego's dialogue to speech with emotion-driven voice settings.
~10,000 free characters ≈ 100 turns. Toggle with TTS_ENABLED env var.
"""
import os

from elevenlabs import VoiceSettings
from elevenlabs.client import AsyncElevenLabs

from models import Emotion

TTS_ENABLED = os.getenv("TTS_ENABLED", "false").lower() in ("true", "1", "yes")
VOICE_ID = os.getenv("ELEVENLABS_VOICE_ID", "JBFqnCBsd6RMkjVDRZzb")

# Voice settings per emotion - pushed apart for noticeable contrast
# stability: lower = more pitch/speed variation (shaky voice)
# similarity_boost: how close to the original voice (lower = more distorted)
# style: expressiveness (higher = more dramatic, costs more latency)
VOICE_SETTINGS = {
    Emotion.CALM:      {"stability": 0.85, "similarity_boost": 0.80, "style": 0.0},
    Emotion.NERVOUS:   {"stability": 0.40, "similarity_boost": 0.70, "style": 0.45},
    Emotion.DEFENSIVE: {"stability": 0.55, "similarity_boost": 0.85, "style": 0.70},
    Emotion.BREAKING:  {"stability": 0.15, "similarity_boost": 0.60, "style": 1.0},
}

# v3 audio tags prepended to text - not spoken, but guide the voice performance
EMOTION_TAGS = {
    Emotion.CALM:      "",
    Emotion.NERVOUS:   "[nervous] [hesitant] ",
    Emotion.DEFENSIVE: "[angry] [aggressive] ",
    Emotion.BREAKING:  "[sad] [crying] [whimpering] ",
}

_client: AsyncElevenLabs | None = None


def _get_client() -> AsyncElevenLabs:
    global _client
    if _client is None:
        _client = AsyncElevenLabs(api_key=os.getenv("ELEVENLABS_API_KEY"))
    return _client


async def synthesize(text: str, emotion: Emotion) -> bytes | None:
    """Convert text to speech with emotion-appropriate voice settings.
    Returns mp3 bytes, or None if TTS is disabled."""
    if not TTS_ENABLED:
        return None

    settings = VOICE_SETTINGS[emotion]
    client = _get_client()

    # Prepend emotion tags (v3 interprets these as performance cues, not spoken text)
    tagged_text = EMOTION_TAGS[emotion] + text

    # collect all chunks from the async iterator
    chunks: list[bytes] = []
    async for chunk in client.text_to_speech.convert(
        voice_id=VOICE_ID,
        text=tagged_text,
        voice_settings=VoiceSettings(
            stability=settings["stability"],
            similarity_boost=settings["similarity_boost"],
            style=settings["style"],
            use_speaker_boost=True,
        ),
        output_format="mp3_44100_64",
        model_id="eleven_v3",
    ):
        chunks.append(chunk)

    return b"".join(chunks)
