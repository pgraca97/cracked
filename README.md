# Cracked

A voice-driven interrogation game built for the Mistral AI Hackathon. You speak aloud to question a suspect in a museum theft case. Your goal: catch him in enough contradictions to prove he's guilty before the 10-minute timer runs out.

## Mistral APIs used

| Component | Model | Purpose |
|---|---|---|
| Speech-to-text | `voxtral-mini-latest` | Transcribes the player's spoken questions |
| Suspect (Diego) | `mistral-medium-latest` | Plays the suspect - lies, deflects, breaks under pressure |
| Judge | `mistral-medium-latest` | Evaluates each turn: extracts facts, detects contradictions, tracks relationship pressure |
| Cleanup | `mistral-small-latest` | Fixes STT artifacts before the player sees their transcribed text |

Diego responds in structured JSON every turn. The judge is a separate call that acts as a referee - it catches contradictions the player surfaces without letting Diego self-report them.

## Tech stack

- **Backend**: FastAPI + python-socketio, Python 3.11
- **Frontend**: Vue 3 + TypeScript + Vite
- **VAD**: `@ricky0123/vad-web` - detects when the player stops speaking
- **TTS**: ElevenLabs (optional, disabled by default)

## Setup

**Requirements**: Python 3.11+, Node.js, pnpm

```bash
# Clone and enter the repo
git clone https://github.com/pgraca97/cracked.git
cd cracked
```

**Backend**

```bash
cd backend
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt

cp .env.example .env
# Fill in MISTRAL_API_KEY in .env

uvicorn main:sio_app --host 0.0.0.0 --port 8000 --reload
```

**Frontend**

```bash
cd frontend
pnpm install
pnpm dev
```

Open `http://localhost:5173`.

## TTS (ElevenLabs)

Disabled by default. To enable, set `TTS_ENABLED=true` and fill in `ELEVENLABS_API_KEY` and `ELEVENLABS_VOICE_ID` in `backend/.env`. Voice settings per emotion state are in `docs/game-design.md`.

## How it works

1. VAD detects end of speech and sends the audio buffer to the backend over Socket.IO.
2. Voxtral transcribes it. A cleanup pass fixes common STT artifacts.
3. The transcript goes to `magistral-medium` (Diego) and `mistral-medium` (judge) in sequence.
4. Diego's dialogue is sent to the frontend immediately. If TTS is enabled, audio follows.
5. The judge's evaluation updates the game state: facts log, contradiction count, relationship pressure, emotion level.
6. Emotion escalates from `calm` → `nervous` → `defensive` → `breaking` as contradictions accumulate.
7. Confession triggers at 3+ contradictions, or at 2+ if the player has also pressed Diego on his relationship with his colleague André.

The full case story, contradiction traps, system prompt, and scoring rules are in `docs/game-design.md`.

## Project structure

```
backend/
  main.py          Socket.IO server and event handlers
  game_engine.py   Turn logic, state updates, scoring
  ai_client.py     Mistral chat, Voxtral transcription, judge call
  tts_client.py    ElevenLabs synthesis
  prompts.py       Diego's system prompt and judge instructions
  models.py        Pydantic models: GameState, DiegoResponse, JudgeResponse

frontend/src/components/
  TitleScreen.vue        Case briefing before the interrogation starts
  GameScreen.vue         Main layout, orchestrates all sub-components
  DialogueBox.vue        Typewriter text display
  EvidencePanel.vue      Caught contradictions and case notes
  MicButton.vue          VAD state indicator
  VerdictScreen.vue      Guilty / Not Guilty choice
  ResultScreen.vue       Score and case outcome
```
