import os
import time

from dotenv import load_dotenv
load_dotenv()

import socketio
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from game_engine import GameEngine
from models import Verdict
import ai_client

app = FastAPI()
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

sio = socketio.AsyncServer(async_mode="asgi", cors_allowed_origins="*")
sio_app = socketio.ASGIApp(sio, other_asgi_app=app)

# One game engine per connected client
games: dict[str, GameEngine] = {}
# Track when each game started (wall-clock)
start_times: dict[str, float] = {}


@sio.event
async def connect(sid, environ):
    games[sid] = GameEngine()
    start_times[sid] = time.time()
    await sio.emit("status", "listening", room=sid)


@sio.event
async def disconnect(sid):
    games.pop(sid, None)
    start_times.pop(sid, None)



# Transcriptions that are just noise artifacts — Voxtral's attempt to make words from nothing
_NOISE_PHRASES = {
    "thank you", "thank you.", "thanks.", "hey", "hey.",
    "bye", "bye.", "you", "the", "oh", "ah", "uh",
    "chin", "hm", "hmm", "mm", "mhm",
}


def _is_noise(text: str) -> bool:
    """Return True if the transcription looks like background noise, not a real question."""
    cleaned = text.strip().lower().rstrip(".!?,")
    if len(cleaned) < 3:
        return True
    if cleaned in _NOISE_PHRASES:
        return True
    # Voxtral transcribing animal sounds, onomatopoeia, etc.
    if all(c == cleaned[0] for c in cleaned.replace(" ", "")):
        return True
    return False


@sio.event
async def player_audio(sid, data):
    """Main game loop — triggered when the frontend sends recorded audio."""
    engine = games.get(sid)
    if engine is None:
        return

    # Don't process audio after confession or past the 10-minute mark
    if engine.state.confession_triggered:
        await sio.emit("status", "listening", room=sid)
        return

    audio_bytes = bytes(data)
    elapsed = time.time() - start_times[sid]

    if elapsed > 600:
        await sio.emit("status", "listening", room=sid)
        return

    # 1. Transcribe
    await sio.emit("status", "transcribing", room=sid)
    try:
        player_text = await ai_client.transcribe(audio_bytes)
    except Exception as exc:
        await sio.emit("error", f"Transcription failed: {exc}", room=sid)
        await sio.emit("status", "listening", room=sid)
        return

    # Drop noise artifacts before they waste an LLM call
    if _is_noise(player_text):
        await sio.emit("status", "listening", room=sid)
        return

    await sio.emit("player_text", player_text, room=sid)

    # 2. Get Diego's response
    await sio.emit("status", "thinking", room=sid)
    try:
        response = await engine.process_turn(player_text, elapsed)
    except Exception as exc:
        await sio.emit("error", f"AI response failed: {exc}", room=sid)
        await sio.emit("status", "listening", room=sid)
        return

    # 3. Send text immediately (masks TTS latency)
    await sio.emit("diego_response", {
        "dialogue": response.dialogue,
        "emotion": response.emotion.value,
        "contradictions": engine.state.contradictions_caught,
        "facts": engine.state.facts_log,
        "confession": engine.state.confession_triggered,
        "turn": engine.state.turn_number,
    }, room=sid)

    # 4. TTS would go here — skipped until final integration

    await sio.emit("status", "listening", room=sid)


@sio.event
async def submit_verdict(sid, data):
    """Player submits their verdict at the end of the interrogation."""
    engine = games.get(sid)
    if engine is None:
        return

    elapsed = time.time() - start_times[sid]
    verdict = Verdict(data.get("verdict", "not_guilty"))
    result = engine.calculate_result(verdict, elapsed)

    await sio.emit("case_result", result.model_dump(), room=sid)
