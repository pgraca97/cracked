import asyncio
import json
import os
import tempfile

from mistralai import Mistral

from models import GameState, DiegoResponse, ChatMessage
from prompts import DIEGO_SYSTEM_PROMPT

API_TIMEOUT = 30  # seconds


_client: Mistral | None = None


def _get_client() -> Mistral:
    global _client
    if _client is None:
        _client = Mistral(api_key=os.environ["MISTRAL_API_KEY"])
    return _client


async def transcribe(audio_bytes: bytes) -> str:
    """Send raw audio to Voxtral and return the transcribed text."""
    client = _get_client()

    # Voxtral expects a file upload — write to a temp file
    with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as f:
        f.write(audio_bytes)
        tmp_path = f.name

    try:
        with open(tmp_path, "rb") as audio_file:
            result = await asyncio.wait_for(
                client.audio.transcriptions.complete_async(
                    model="voxtral-mini-transcribe-2507",
                    file={
                        "file_name": "audio.wav",
                        "content": audio_file,
                    },
                    language="en",
                    # Bias toward game-specific names so "André" doesn't become "Andrea"
                    context_bias=["André", "Diego", "Fonseca", "Star Diamond"],
                ),
                timeout=API_TIMEOUT,
            )
        return result.text.strip()
    finally:
        os.unlink(tmp_path)


async def chat(game_state: GameState, player_text: str) -> DiegoResponse:
    """Send the conversation to Mistral and parse Diego's JSON response."""
    client = _get_client()

    state_summary = json.dumps({
        "turn_number": game_state.turn_number,
        "time_elapsed_seconds": game_state.time_elapsed_seconds,
        "emotion_state": game_state.emotion_state.value,
        "contradictions_caught": game_state.contradictions_caught,
        "relationship_mentioned": game_state.relationship_mentioned,
        "confession_triggered": game_state.confession_triggered,
    })

    messages = [
        {"role": "system", "content": f"{DIEGO_SYSTEM_PROMPT}\n\nCurrent game state: {state_summary}"},
    ]

    # Replay recent conversation history (keep last 20 messages to stay within token limits)
    recent = game_state.conversation_history[-20:]
    for msg in recent:
        messages.append({"role": msg.role, "content": msg.content})

    # New player question
    messages.append({"role": "user", "content": player_text})

    # Try up to 2 times (retry once on malformed JSON)
    last_error: Exception | None = None
    for _ in range(2):
        response = await asyncio.wait_for(
            client.chat.complete_async(
                model="mistral-small-latest",
                messages=messages,
                response_format={"type": "json_object"},
                temperature=0.7,
            ),
            timeout=API_TIMEOUT,
        )
        raw = response.choices[0].message.content
        try:
            data = json.loads(raw)
            return DiegoResponse(**data)
        except (json.JSONDecodeError, ValueError) as exc:
            last_error = exc

    raise ValueError(f"Mistral returned invalid JSON after retry: {last_error}")
