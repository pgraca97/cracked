"""
Smoke tests for Mistral APIs. Run from backend/:
    python test_apis.py

Tests Voxtral transcription and Mistral chat (JSON mode as Diego).
Does NOT test ElevenLabs — saving credits for the demo.
"""
import asyncio
import os
import json

from dotenv import load_dotenv
load_dotenv()

from mistralai import Mistral
from models import GameState, DiegoResponse
from prompts import DIEGO_SYSTEM_PROMPT


async def test_mistral_chat():
    """Send a single question to Mistral as the detective, verify JSON response."""
    print("=== Mistral Chat (Diego) ===")
    client = Mistral(api_key=os.environ["MISTRAL_API_KEY"])

    state = GameState()
    state_json = json.dumps({
        "turn_number": 1,
        "time_elapsed_seconds": 10.0,
        "emotion_state": state.emotion_state.value,
        "contradictions_caught": [],
        "relationship_pressure": 0,
        "confession_triggered": False,
        "facts_log": [],
    })

    messages = [
        {"role": "system", "content": f"{DIEGO_SYSTEM_PROMPT}\n\nCurrent game state: {state_json}"},
        {"role": "user", "content": "Where were you last night between 9 and 11 PM?"},
    ]

    response = await client.chat.complete_async(
        model="mistral-small-latest",
        messages=messages,
        response_format={"type": "json_object"},
        temperature=0.7,
    )

    raw = response.choices[0].message.content
    print(f"Raw response:\n{raw}\n")

    data = json.loads(raw)
    diego = DiegoResponse(**data)
    print(f"Dialogue: {diego.dialogue}")
    print(f"Emotion:  {diego.emotion.value}")
    print(f"Thought:  {diego.internal_thought}")
    print(f"Facts:    {diego.facts_mentioned}")
    print("PASS\n")


async def test_voxtral_transcription():
    """Generate a short WAV with a spoken phrase and transcribe it via Voxtral."""
    print("=== Voxtral Transcription ===")

    # Generate a minimal valid WAV file with silence (1 second, 16kHz mono)
    # This tests that the API accepts our request format
    import struct
    import tempfile

    sample_rate = 16000
    duration = 1
    num_samples = sample_rate * duration
    # Silent audio
    audio_data = b'\x00\x00' * num_samples

    # Build WAV header
    wav = bytearray()
    wav.extend(b'RIFF')
    wav.extend(struct.pack('<I', 36 + len(audio_data)))
    wav.extend(b'WAVE')
    wav.extend(b'fmt ')
    wav.extend(struct.pack('<I', 16))       # chunk size
    wav.extend(struct.pack('<H', 1))        # PCM
    wav.extend(struct.pack('<H', 1))        # mono
    wav.extend(struct.pack('<I', sample_rate))
    wav.extend(struct.pack('<I', sample_rate * 2))  # byte rate
    wav.extend(struct.pack('<H', 2))        # block align
    wav.extend(struct.pack('<H', 16))       # bits per sample
    wav.extend(b'data')
    wav.extend(struct.pack('<I', len(audio_data)))
    wav.extend(audio_data)

    client = Mistral(api_key=os.environ["MISTRAL_API_KEY"])

    with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as f:
        f.write(wav)
        tmp_path = f.name

    try:
        result = await client.audio.transcriptions.complete_async(
            model="voxtral-mini-transcribe-2507",
            file={
                "file_name": "test.wav",
                "content": open(tmp_path, "rb"),
            },
        )
        print(f"Transcription result: '{result.text}'")
        print("PASS (API accepted the request)\n")
    finally:
        os.unlink(tmp_path)


async def main():
    await test_mistral_chat()
    await test_voxtral_transcription()
    print("All tests passed!")


if __name__ == "__main__":
    asyncio.run(main())
