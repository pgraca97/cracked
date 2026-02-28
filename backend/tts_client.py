"""
ElevenLabs TTS — NOT active yet.
Only enable for final integration and demo. ~100 turns of credits total.
"""
import os

from models import Emotion

# Voice settings per emotion (from game-design.md)
VOICE_SETTINGS = {
    Emotion.CALM:      {"stability": 0.75, "similarity_boost": 0.75, "style": 0.0},
    Emotion.NERVOUS:   {"stability": 0.50, "similarity_boost": 0.75, "style": 0.3},
    Emotion.DEFENSIVE: {"stability": 0.60, "similarity_boost": 0.80, "style": 0.6},
    Emotion.BREAKING:  {"stability": 0.30, "similarity_boost": 0.70, "style": 0.8},
}

VOICE_ID = os.getenv("ELEVENLABS_VOICE_ID", "JBFqnCBsd6RMkjVDRZzb")


async def synthesize(text: str, emotion: Emotion) -> bytes | None:
    """Convert text to speech. Returns None while TTS is disabled."""
    # TODO: enable when text loop is stable and ready for demo
    return None
