import os
import time

from dotenv import load_dotenv
load_dotenv()

import socketio
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from realtime_handler import RealtimeSession
from models import Verdict

app = FastAPI()
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

sio = socketio.AsyncServer(async_mode="asgi", cors_allowed_origins="*")
sio_app = socketio.ASGIApp(sio, other_asgi_app=app)

# One realtime session per connected client
sessions: dict[str, RealtimeSession] = {}


@sio.event
async def connect(sid, environ):
    sessions[sid] = RealtimeSession(sio, sid)
    await sio.emit("state_change", "listening", room=sid)


@sio.event
async def disconnect(sid):
    session = sessions.pop(sid, None)
    if session:
        await session.cleanup()


@sio.event
async def speech_start(sid, data=None):
    """VAD detected speech onset — start streaming audio to Voxtral."""
    session = sessions.get(sid)
    if session:
        await session.start_speech()


@sio.event
async def audio_chunk(sid, data):
    """Raw PCM audio chunk from the frontend AudioWorklet."""
    session = sessions.get(sid)
    if session:
        await session.feed_audio(bytes(data))


@sio.event
async def speech_end(sid, data=None):
    """VAD detected silence — close the audio stream and trigger Mistral."""
    session = sessions.get(sid)
    if session:
        await session.end_speech()


@sio.event
async def barge_in(sid, data=None):
    """Player started speaking while Diego was responding — cut him off."""
    session = sessions.get(sid)
    if session:
        await session.handle_barge_in()


@sio.event
async def submit_verdict(sid, data):
    """Player submits their verdict at the end of the interrogation."""
    session = sessions.get(sid)
    if session is None:
        return

    elapsed = session.elapsed
    verdict = Verdict(data.get("verdict", "not_guilty"))
    result = session.engine.calculate_result(verdict, elapsed)

    await sio.emit("case_result", result.model_dump(), room=sid)
