import asyncio
import json
import os
import time
from enum import Enum
from typing import AsyncIterator
from urllib.parse import urlencode

from mistralai import Mistral
from mistralai.extra.realtime import UnknownRealtimeEvent
from mistralai.extra.realtime.connection import RealtimeConnection
from mistralai.models import (
    AudioFormat,
    RealtimeTranscriptionError,
    RealtimeTranscriptionSessionCreated,
    TranscriptionStreamDone,
    TranscriptionStreamTextDelta,
)

try:
    from websockets.asyncio.client import connect as ws_connect
except ImportError:
    raise ImportError("websockets >= 13.0 required: pip install 'mistralai[realtime]'")

from game_engine import GameEngine
from models import DiegoResponse, ChatMessage
import ai_client
import tts_client


class SessionState(str, Enum):
    LISTENING = "listening"
    PLAYER_SPEAKING = "player_speaking"
    PROCESSING = "processing"
    DIEGO_SPEAKING = "diego_speaking"


# Noise filter
_NOISE_PHRASES = {
    "thank you", "thank you.", "thanks.", "hey", "hey.",
    "bye", "bye.", "you", "the", "oh", "ah", "uh",
    "chin", "hm", "hmm", "mm", "mhm",
}


def _is_noise(text: str) -> bool:
    cleaned = text.strip().lower().rstrip(".!?,")
    if len(cleaned) < 2:
        return True
    if cleaned in _NOISE_PHRASES:
        return True
    if all(c == cleaned[0] for c in cleaned.replace(" ", "")):
        return True
    return False


async def _audio_queue_iter(queue: asyncio.Queue) -> AsyncIterator[bytes]:
    """Yield audio chunks from a queue until None sentinel."""
    while True:
        chunk = await queue.get()
        if chunk is None:
            break
        yield chunk


class RealtimeSession:
    """Manages a single client's realtime streaming session."""

    # Voxtral streaming delay — higher = more accurate, lower = more responsive
    # 1000ms is a good balance for voice assistant use cases (per Mistral docs)
    STREAMING_DELAY_MS = 1000

    def __init__(self, sio, sid: str):
        self.sio = sio
        self.sid = sid
        self.engine = GameEngine()
        self.state = SessionState.LISTENING
        self.start_time = time.time()

        # Audio streaming
        self.audio_queue: asyncio.Queue[bytes | None] = asyncio.Queue(maxsize=200)
        self.voxtral_task: asyncio.Task | None = None
        self.current_transcription = ""

        # Mistral streaming
        self.mistral_task: asyncio.Task | None = None
        self.partial_dialogue = ""

        # Track whether barge-in is active to suppress leftover diego_tokens
        self.barge_in_active = False

        self._client: Mistral | None = None
        self.audio_format = AudioFormat(encoding="pcm_s16le", sample_rate=16000)

    def _get_client(self) -> Mistral:
        if self._client is None:
            self._client = Mistral(api_key=os.environ["MISTRAL_API_KEY"])
        return self._client

    @property
    def elapsed(self) -> float:
        return time.time() - self.start_time

    async def _set_state(self, new_state: SessionState):
        self.state = new_state
        await self.sio.emit("state_change", new_state.value, room=self.sid)

    async def start_speech(self):
        """Called when VAD detects speech onset."""
        if self.engine.state.confession_triggered:
            return
        if self.elapsed > 600:
            return

        # If Diego is speaking, this is a barge-in
        if self.state == SessionState.DIEGO_SPEAKING:
            await self.handle_barge_in()

        # Cancel any previous Voxtral session
        if self.voxtral_task and not self.voxtral_task.done():
            self.voxtral_task.cancel()
            try:
                await self.voxtral_task
            except (asyncio.CancelledError, Exception):
                pass

        # Fresh queue and transcription for the new utterance
        self.audio_queue = asyncio.Queue(maxsize=200)
        self.current_transcription = ""
        self.barge_in_active = False

        await self._set_state(SessionState.PLAYER_SPEAKING)

        # Launch Voxtral realtime session in background
        self.voxtral_task = asyncio.create_task(self._run_voxtral())

    async def feed_audio(self, data: bytes):
        """Called for each audio chunk from the frontend."""
        if self.state != SessionState.PLAYER_SPEAKING:
            return
        try:
            self.audio_queue.put_nowait(data)
        except asyncio.QueueFull:
            try:
                self.audio_queue.get_nowait()
            except asyncio.QueueEmpty:
                pass
            self.audio_queue.put_nowait(data)

    async def end_speech(self):
        """Called when VAD detects silence — close the audio stream."""
        if self.state != SessionState.PLAYER_SPEAKING:
            return

        # Send sentinel to close the async iterator
        try:
            self.audio_queue.put_nowait(None)
        except asyncio.QueueFull:
            try:
                self.audio_queue.get_nowait()
            except asyncio.QueueEmpty:
                pass
            self.audio_queue.put_nowait(None)

        # Wait for Voxtral to finish processing
        if self.voxtral_task:
            try:
                await asyncio.wait_for(self.voxtral_task, timeout=8.0)
            except (asyncio.TimeoutError, asyncio.CancelledError, Exception) as exc:
                print(f"[realtime] Voxtral finish error: {exc}")

        # Emit final transcription
        full_text = self.current_transcription.strip()
        if full_text:
            await self.sio.emit("transcription_done", {"full_text": full_text}, room=self.sid)

        # Check for noise
        if not full_text or _is_noise(full_text):
            await self._set_state(SessionState.LISTENING)
            return

        # Trigger Mistral
        await self._process_turn(full_text)

    async def handle_barge_in(self):
        """Player started speaking while Diego was responding — cut him off."""
        self.barge_in_active = True

        # Cancel the Mistral streaming task
        if self.mistral_task and not self.mistral_task.done():
            self.mistral_task.cancel()
            try:
                await self.mistral_task
            except (asyncio.CancelledError, Exception):
                pass

        # Save partial response to conversation history if we got anything
        if self.partial_dialogue.strip():
            await self.sio.emit("diego_interrupted", {
                "partial_dialogue": self.partial_dialogue
            }, room=self.sid)
            self.engine.state.conversation_history.append(
                ChatMessage(role="assistant", content=f"{self.partial_dialogue} [interrupted]")
            )

        self.partial_dialogue = ""

    async def _run_voxtral(self):
        """Run a Voxtral realtime transcription session for one utterance.

        Bypasses the SDK's transcribe_stream() to inject language="en" as a
        WebSocket query parameter — the SDK doesn't expose it yet, but the
        API supports it (docs only exclude diarize from realtime).
        """
        client = self._get_client()
        api_key = os.environ["MISTRAL_API_KEY"]

        # Build WebSocket URL with language param
        base = os.environ.get("MISTRAL_BASE_URL", "https://api.mistral.ai")
        base = base.rstrip("/")
        params = urlencode({
            "model": "voxtral-mini-transcribe-realtime-2602",
            "language": "en",
            "context_bias": ",".join([
                "André", "Diego", "Fonseca", "Lopes",
                "Marcus", "Webb", "Sarah", "Mitchell",
                "James", "Barlow", "Eleanor", "Voss",
                "gala", "Municipal", "diamond", "corridor",
                "locker", "backpack",
            ]),
        })
        url = f"{base}/v1/audio/transcriptions/realtime?{params}"
        url = url.replace("https://", "wss://").replace("http://", "ws://")

        websocket = None
        try:
            websocket = await ws_connect(
                url,
                additional_headers={"Authorization": f"Bearer {api_key}"},
                open_timeout=10.0,
            )

            # Wait for session.created handshake
            from mistralai.extra.realtime.connection import parse_realtime_event
            raw = await asyncio.wait_for(websocket.recv(), timeout=10.0)
            text = raw.decode("utf-8") if isinstance(raw, (bytes, bytearray)) else raw
            payload = json.loads(text)
            event = parse_realtime_event(payload)

            if not isinstance(event, RealtimeTranscriptionSessionCreated):
                print(f"[voxtral-rt] Unexpected handshake event: {payload}")
                return

            print(f"[voxtral-rt] Session created for {self.sid}")

            # Configure audio format and streaming delay via session update
            await websocket.send(json.dumps({
                "type": "session.update",
                "session": {
                    "audio_format": {
                        "encoding": "pcm_s16le",
                        "sample_rate": 16000,
                    },
                    "target_streaming_delay_ms": self.STREAMING_DELAY_MS,
                },
            }))

            # Background task: send audio chunks
            async def send_audio():
                try:
                    async for chunk in _audio_queue_iter(self.audio_queue):
                        if websocket.close_code is not None:
                            break
                        import base64
                        msg = json.dumps({
                            "type": "input_audio.append",
                            "audio": base64.b64encode(chunk).decode("ascii"),
                        })
                        await websocket.send(msg)
                    # Flush + end
                    await websocket.send(json.dumps({"type": "input_audio.flush"}))
                    await websocket.send(json.dumps({"type": "input_audio.end"}))
                except Exception as exc:
                    print(f"[voxtral-rt] Send error: {exc}")

            send_task = asyncio.create_task(send_audio())

            try:
                async for msg in websocket:
                    text = msg.decode("utf-8") if isinstance(msg, (bytes, bytearray)) else msg
                    try:
                        data = json.loads(text)
                    except Exception:
                        continue
                    event = parse_realtime_event(data)

                    if isinstance(event, TranscriptionStreamTextDelta):
                        self.current_transcription += event.text
                        await self.sio.emit("transcription_delta", {"text": event.text}, room=self.sid)
                    elif isinstance(event, TranscriptionStreamDone):
                        print(f"[voxtral-rt] Done: '{self.current_transcription.strip()}'")
                        break
                    elif isinstance(event, RealtimeTranscriptionError):
                        print(f"[voxtral-rt] Error: {event}")
                        await self.sio.emit("error", f"Transcription error: {event}", room=self.sid)
                        break
                    elif isinstance(event, UnknownRealtimeEvent):
                        continue
            finally:
                send_task.cancel()
                try:
                    await send_task
                except asyncio.CancelledError:
                    pass

        except asyncio.CancelledError:
            raise
        except Exception as exc:
            print(f"[voxtral-rt] Exception: {exc}")
            await self.sio.emit("error", f"Realtime transcription failed: {exc}", room=self.sid)
        finally:
            if websocket and websocket.close_code is None:
                await websocket.close()

    async def _process_turn(self, player_text: str):
        """After transcription is done, run Mistral (streaming) + judge."""
        await self._set_state(SessionState.PROCESSING)
        self.partial_dialogue = ""
        self.barge_in_active = False

        # Launch streaming Mistral response
        self.mistral_task = asyncio.create_task(self._run_mistral_stream(player_text))

    async def _run_mistral_stream(self, player_text: str):
        """Stream Diego's response token by token, then run the judge."""
        try:
            self.engine.state.turn_number += 1
            self.engine.state.time_elapsed_seconds = self.elapsed

            full_response: DiegoResponse | None = None

            async for token, response in ai_client.chat_stream(self.engine.state, player_text):
                # Stop emitting if barge-in happened
                if self.barge_in_active:
                    break

                if response is not None:
                    full_response = response
                    break
                if token:
                    self.partial_dialogue += token
                    await self.sio.emit("diego_token", {"token": token}, room=self.sid)
                    if self.state != SessionState.DIEGO_SPEAKING:
                        await self._set_state(SessionState.DIEGO_SPEAKING)

            # If we were interrupted by barge-in, don't process further
            if self.barge_in_active:
                return

            if full_response is None:
                await self.sio.emit("error", "Failed to get Diego's response", room=self.sid)
                await self._set_state(SessionState.LISTENING)
                return

            # Run the judge (non-streaming, fast)
            judge = await ai_client.judge_turn(
                self.engine.state.facts_log,
                self.engine.state.conversation_history,
                player_text,
                full_response,
            )

            # Update game state
            self.engine._update_state(full_response, judge)

            # Append to conversation history
            enhanced = judge.player_text_enhanced or player_text
            self.engine.state.conversation_history.append(
                ChatMessage(role="user", content=enhanced)
            )
            self.engine.state.conversation_history.append(
                ChatMessage(role="assistant", content=full_response.dialogue)
            )

            # Emit complete response with game state
            await self.sio.emit("diego_done", {
                "dialogue": full_response.dialogue,
                "emotion": full_response.emotion.value,
                "contradictions": list(self.engine.state.contradictions_caught.values()),
                "facts": self.engine.state.facts_log,
                "confession": self.engine.state.confession_triggered,
                "turn": self.engine.state.turn_number,
                "tts_enabled": tts_client.TTS_ENABLED,
            }, room=self.sid)

            # TTS (if enabled)
            try:
                audio = await tts_client.synthesize(full_response.dialogue, full_response.emotion)
                if audio:
                    await self.sio.emit("diego_audio", audio, room=self.sid)
            except Exception as exc:
                print(f"[TTS] Failed (non-fatal): {exc}")

            # Transition state
            if self.engine.state.confession_triggered:
                await self._set_state(SessionState.LISTENING)
                await self.sio.emit("state_change", "confession", room=self.sid)
            else:
                await self._set_state(SessionState.LISTENING)

        except asyncio.CancelledError:
            raise
        except Exception as exc:
            print(f"[realtime] Mistral stream error: {exc}")
            await self.sio.emit("error", f"AI response failed: {exc}", room=self.sid)
            await self._set_state(SessionState.LISTENING)

    async def cleanup(self):
        """Cancel all running tasks on disconnect."""
        for task in [self.voxtral_task, self.mistral_task]:
            if task and not task.done():
                task.cancel()
                try:
                    await task
                except (asyncio.CancelledError, Exception):
                    pass
