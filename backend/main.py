import asyncio
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
import tts_client

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



# Transcriptions that are just noise artifacts - Voxtral's attempt to make words from nothing
_NOISE_PHRASES = {
    "thank you", "thank you.", "thanks.", "hey", "hey.",
    "bye", "bye.", "you", "the", "oh", "ah", "uh",
    "chin", "hm", "hmm", "mm", "mhm",
}


def _is_noise(text: str) -> bool:
    """Return True if the transcription looks like background noise, not a real question."""
    cleaned = text.strip().lower().rstrip(".!?,")
    if len(cleaned) < 2:
        return True
    if cleaned in _NOISE_PHRASES:
        return True
    # Voxtral transcribing animal sounds, onomatopoeia, etc.
    if all(c == cleaned[0] for c in cleaned.replace(" ", "")):
        return True
    return False


@sio.event
async def player_audio(sid, data):
    """Main game loop - triggered when the frontend sends recorded audio."""
    engine = games.get(sid)
    if engine is None:
        return

    # Don't process audio after confession or past the 10-minute mark
    if engine.state.confession_triggered:
        return

    audio_bytes = bytes(data)
    elapsed = time.time() - start_times[sid]

    if elapsed > 600:
        return

    # 1. Transcribe
    await sio.emit("status", "transcribing", room=sid)
    try:
        raw_text = await ai_client.transcribe(audio_bytes)
    except Exception as exc:
        await sio.emit("error", f"Transcription failed: {exc}", room=sid)
        await sio.emit("status", "listening", room=sid)
        return

    # Drop noise artifacts before they waste LLM calls
    if _is_noise(raw_text):
        await sio.emit("status", "listening", room=sid)
        return

    # 2. Show raw text immediately, clean in parallel with Diego
    await sio.emit("player_text", raw_text, room=sid)
    await sio.emit("status", "thinking", room=sid)

    # Run cleanup + Diego in parallel - Diego doesn't need the cleaned text
    cleanup_task = asyncio.create_task(
        ai_client.clean_transcription(raw_text, engine.state.conversation_history[-6:])
    )

    try:
        response = await engine.get_diego_response(raw_text, elapsed)
    except Exception as exc:
        cleanup_task.cancel()
        await sio.emit("error", f"AI response failed: {exc}", room=sid)
        await sio.emit("status", "listening", room=sid)
        return

    # If cleanup finished, update the player text shown in the UI
    try:
        player_text = await asyncio.wait_for(asyncio.shield(cleanup_task), timeout=0.1)
    except (asyncio.TimeoutError, Exception):
        player_text = raw_text
    if player_text != raw_text:
        await sio.emit("player_text", player_text, room=sid)

    # 3. Emit text IMMEDIATELY - don't wait for judge or TTS
    await sio.emit("diego_response", {
        "dialogue": response.dialogue,
        "emotion": response.emotion.value,
        "contradictions": list(engine.state.contradictions_caught.values()),
        "facts": engine.state.facts_log,
        "confession": engine.state.confession_triggered,
        "turn": engine.state.turn_number,
        "tts_enabled": tts_client.TTS_ENABLED,
    }, room=sid)

    # 4. Run judge + TTS in parallel - both depend on Diego's response, not each other
    async def _synthesize_and_emit():
        try:
            audio = await tts_client.synthesize(response.dialogue, response.emotion)
            if audio:
                await sio.emit("diego_audio", audio, room=sid)
        except Exception:
            pass  # TTS failure is non-fatal

    async def _run_judge():
        try:
            await engine.run_judge_and_update(player_text, response)
            # Emit updated state as soon as judge finishes (don't wait for TTS)
            await sio.emit("state_update", {
                "emotion": response.emotion.value,
                "contradictions": list(engine.state.contradictions_caught.values()),
                "facts": engine.state.facts_log,
                "confession": engine.state.confession_triggered,
            }, room=sid)
        except Exception:
            pass  # Judge failure is non-fatal, state just won't update

    await asyncio.gather(_synthesize_and_emit(), _run_judge())

    if not engine.state.confession_triggered:
        await sio.emit("status", "listening", room=sid)
    else:
        await sio.emit("status", "confession", room=sid)


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
