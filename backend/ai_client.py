import asyncio
import json
import os
import re
import tempfile

from mistralai import Mistral

from models import GameState, DiegoResponse, JudgeResponse, ChatMessage
from prompts import DIEGO_SYSTEM_PROMPT, JUDGE_SYSTEM_PROMPT, CLEANUP_PROMPT_TEMPLATE

API_TIMEOUT = 45  # seconds (magistral needs more time for reasoning)

# Diego model: supports "mistral-small-latest" or "magistral-small-latest" (reasoning)
DIEGO_MODEL = os.environ.get("DIEGO_MODEL", "mistral-small-latest")
print(f"Using Diego model: {DIEGO_MODEL}")
# Judge/cleanup: always cheap and fast
JUDGE_MODEL = "mistral-small-latest"


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
                    model="voxtral-mini-2602",
                    file={
                        "file_name": "audio.wav",
                        "content": audio_file,
                    },
                    language="en",
                    # Bias toward game-specific proper nouns — prevents common mistranscriptions
                    context_bias=[
                        "André", "Diego", "Fonseca", "Lopes",
                        "Marcus", "Webb", "Sarah", "Mitchell",
                        "James", "Barlow", "Eleanor", "Voss",
                        "gala", "Municipal", "diamond", "corridor",
                        "locker", "backpack",
                    ],
                ),
                timeout=API_TIMEOUT,
            )
        return result.text.strip()
    finally:
        os.unlink(tmp_path)


def _extract_json_from_text(text: str) -> str:
    """Try to extract a JSON object from text that might contain markdown fences or other wrapping.

    Uses brace counting instead of regex to handle arbitrarily nested JSON.
    """
    text = text.strip()
    if not text:
        return ""

    # Already valid JSON?
    if text.startswith("{"):
        return text

    # Wrapped in markdown code block: ```json\n{...}\n```  — use greedy match
    match = re.search(r'```(?:json)?\s*(\{.*\})\s*```', text, re.DOTALL)
    if match:
        return match.group(1)

    # Find JSON object by brace counting — handles arbitrary nesting depth
    start = text.find("{")
    if start == -1:
        return ""  # No JSON object found at all

    depth = 0
    in_string = False
    escape = False
    for i in range(start, len(text)):
        c = text[i]
        if escape:
            escape = False
            continue
        if c == '\\' and in_string:
            escape = True
            continue
        if c == '"' and not escape:
            in_string = not in_string
            continue
        if in_string:
            continue
        if c == '{':
            depth += 1
        elif c == '}':
            depth -= 1
            if depth == 0:
                return text[start:i + 1]

    # Unbalanced braces — return from first { to end and hope json.loads figures it out
    return text[start:]


def _get_chunk_attr(chunk, attr: str, default=None):
    """Get attribute from a chunk that could be a dict or SDK object."""
    if isinstance(chunk, dict):
        return chunk.get(attr, default)
    return getattr(chunk, attr, default)


def _parse_magistral_response(content) -> tuple[str, str]:
    """Extract (internal_thought, json_text) from a magistral reasoning response.

    Handles multiple response formats from the SDK:
    - str: plain text (non-reasoning fallback, or old <think> tag format)
    - list of typed chunks with "thinking" and "text" types (SDK 1.12+, model -2509)
    - SDK objects with .type, .thinking, .text attributes
    """
    internal_thought = ""
    json_text = ""
    all_text_parts = []

    # Debug: log the raw content structure
    print(f"[magistral] content type={type(content).__name__}, "
          f"is_str={isinstance(content, str)}, is_list={isinstance(content, list)}")

    if isinstance(content, str):
        # Log the actual string so we can see what magistral returned
        print(f"[magistral] string content (first 500 chars): {repr(content[:500])}")
        # Could be old <think>...</think> format or plain text
        if "<think>" in content:
            think_match = re.search(r'<think>(.*?)</think>(.*)', content, re.DOTALL)
            if think_match:
                internal_thought = think_match.group(1).strip()
                remaining = think_match.group(2).strip()
                return internal_thought, _extract_json_from_text(remaining)
        return "", _extract_json_from_text(content)

    if not content:
        print("[magistral] content is empty/None")
        return "", ""

    # Handle both list and single object
    chunks = content if isinstance(content, list) else [content]

    print(f"[magistral] {len(chunks)} chunks: "
          f"{[_get_chunk_attr(c, 'type', '?') for c in chunks]}")

    for chunk in chunks:
        chunk_type = _get_chunk_attr(chunk, "type")

        if chunk_type == "thinking":
            thinking_parts = _get_chunk_attr(chunk, "thinking", [])
            for part in (thinking_parts or []):
                text = _get_chunk_attr(part, "text", "")
                if text:
                    internal_thought += text
                    all_text_parts.append(text)
        elif chunk_type == "text":
            text = _get_chunk_attr(chunk, "text", "")
            if text:
                json_text += text
            else:
                print(f"[magistral] text chunk had empty text, chunk={repr(chunk)[:200]}")
        else:
            # Unknown chunk type — might contain useful text
            text = _get_chunk_attr(chunk, "text", "")
            if text:
                all_text_parts.append(text)
            print(f"[magistral] unknown chunk type={chunk_type}, chunk={repr(chunk)[:200]}")

    # Log what we extracted
    print(f"[magistral] thinking={len(internal_thought)} chars, "
          f"json_text={len(json_text)} chars, "
          f"json_text_preview={repr(json_text[:200]) if json_text else 'EMPTY'}")

    json_text = _extract_json_from_text(json_text)

    # Fallback: if text chunk was empty, look for JSON in thinking chunks
    if not json_text and all_text_parts:
        combined = "\n".join(all_text_parts)
        json_text = _extract_json_from_text(combined)
        if json_text:
            print(f"[magistral] found JSON in thinking chunks instead (fallback)")

    return internal_thought, json_text


def _clean_dialogue(text: str) -> str:
    """Strip typographic artifacts — dialogue should read as natural spoken language."""
    text = text.replace("—", " -- ")   # em dash → spoken pause
    text = text.replace("–", " -- ")   # en dash
    text = text.replace("**", "")      # bold markdown
    text = text.replace("*", "")       # italic markdown
    # Collapse multiple spaces
    while "  " in text:
        text = text.replace("  ", " ")
    return text.strip()


async def chat(game_state: GameState, player_text: str) -> DiegoResponse:
    """Send the conversation to Mistral and parse Diego's JSON response."""
    client = _get_client()

    state_summary = json.dumps({
        "turn_number": game_state.turn_number,
        "time_elapsed_seconds": game_state.time_elapsed_seconds,
        "emotion_state": game_state.emotion_state.value,
        "detective_tone": game_state.detective_tone.value,
        "contradictions_caught": list(game_state.contradictions_caught.keys()),
        "relationship_pressure": game_state.relationship_pressure,
        "confession_triggered": game_state.confession_triggered,
        "facts_log": game_state.facts_log[-30:],  # Diego sees his own prior claims for consistency
    })

    messages = [
        {"role": "system", "content": f"{DIEGO_SYSTEM_PROMPT}\n\nCurrent game state: {state_summary}"},
    ]

    # Replay recent conversation history (keep last 20 messages to stay within token limits)
    recent = game_state.conversation_history[-20:]
    for msg in recent:
        messages.append({"role": msg.role, "content": msg.content})

    # New player question — for magistral, add a JSON reminder since it tends to respond in plain text
    is_magistral = DIEGO_MODEL.startswith("magistral")
    if is_magistral:
        messages.append({"role": "user", "content": f"{player_text}\n\n[Respond ONLY with a valid JSON object. No plain text outside the JSON.]"})
    else:
        messages.append({"role": "user", "content": player_text})

    # Magistral is flakier with JSON — give it more attempts
    max_attempts = 3 if is_magistral else 2
    last_error: Exception | None = None

    for attempt in range(max_attempts):
        kwargs = {
            "model": DIEGO_MODEL,
            "messages": messages,
            "temperature": 0.7,
        }
        # json_object mode works with mistral models; magistral uses free-form output
        if not is_magistral:
            kwargs["response_format"] = {"type": "json_object"}
        else:
            # Opt out of magistral's default system prompt (encourages Markdown/LaTeX)
            # — our own system prompt already has all the instructions Diego needs
            kwargs["prompt_mode"] = None

        response = await asyncio.wait_for(
            client.chat.complete_async(**kwargs),
            timeout=API_TIMEOUT,
        )

        raw_content = response.choices[0].message.content

        try:
            if is_magistral:
                internal_thought, raw_json = _parse_magistral_response(raw_content)
                if not raw_json or not raw_json.strip():
                    # Log what we got so we can debug
                    content_type = type(raw_content).__name__
                    content_preview = repr(raw_content)[:200] if raw_content else "None"
                    print(f"[magistral attempt {attempt+1}] Empty JSON. Content type={content_type}, preview={content_preview}")
                    raise ValueError(f"Empty text chunk from magistral (type={content_type})")
                data = json.loads(raw_json)
                # Magistral's thinking becomes the internal_thought
                if internal_thought and not data.get("internal_thought"):
                    data["internal_thought"] = internal_thought
            else:
                if not raw_content or not raw_content.strip():
                    raise ValueError("Empty response from model")
                data = json.loads(raw_content)

            # Model sometimes returns a JSON array instead of an object
            if isinstance(data, list):
                data = data[0] if data and isinstance(data[0], dict) else {}

            resp = DiegoResponse(**data)
            resp.dialogue = _clean_dialogue(resp.dialogue)
            return resp
        except (json.JSONDecodeError, ValueError, TypeError) as exc:
            last_error = exc
            if is_magistral:
                print(f"[magistral attempt {attempt+1}] Parse error: {exc}")

    raise ValueError(f"Mistral returned invalid JSON after {max_attempts} attempts: {last_error}")


async def judge_turn(
    facts_log: list[str],
    conversation_history: list[ChatMessage],
    player_text: str,
    diego_response: DiegoResponse,
) -> JudgeResponse:
    """Separate cheap call that evaluates the turn: facts, contradictions, relationship pressure."""
    client = _get_client()

    # Build context for the judge
    recent_history = conversation_history[-10:]
    history_text = "\n".join(
        f"{'Detective' if m.role == 'user' else 'Diego'}: {m.content}"
        for m in recent_history
    )

    facts_text = "\n".join(f"- {f}" for f in facts_log[-20:]) if facts_log else "(no prior facts)"

    user_prompt = f"""## Previous facts on record:
{facts_text}

## Recent conversation:
{history_text}

## This turn:
Detective: {player_text}
Diego: {diego_response.dialogue}

Evaluate this turn."""

    messages = [
        {"role": "system", "content": JUDGE_SYSTEM_PROMPT},
        {"role": "user", "content": user_prompt},
    ]

    try:
        response = await asyncio.wait_for(
            client.chat.complete_async(
                model=JUDGE_MODEL,
                messages=messages,
                response_format={"type": "json_object"},
                temperature=0.1,  # Low temp for consistent evaluation
            ),
            timeout=API_TIMEOUT,
        )
        raw = response.choices[0].message.content
        data = json.loads(raw)
        return JudgeResponse(**data)
    except Exception:
        # If judge fails, return safe defaults — don't break the game
        return JudgeResponse()


# TODO: Cleanup logic commented out — not working properly yet, will revisit
# # Known STT errors that happen repeatedly — fix these deterministically before LLM cleanup
# _STT_FIXES = [
#     # "Soy" is Spanish, Voxtral confuses it with English "So" at sentence boundaries
#     (re.compile(r'\bSoy\b'), 'So'),
#     (re.compile(r'\bsoy\b'), 'so'),
#     # Accent on André
#     (re.compile(r'\bAndre\b'), 'André'),
#     # Common name mishearing
#     (re.compile(r'\bDio\b'), 'Diego'),
# ]
# 
# 
# def _apply_stt_fixes(text: str) -> str:
#     """Fast deterministic fixes for known repeated STT errors."""
#     for pattern, replacement in _STT_FIXES:
#         text = pattern.sub(replacement, text)
#     return text
# 
# 
# async def clean_transcription(
#     raw_text: str,
#     recent_history: list[ChatMessage],
# ) -> str:
#     """Quick cleanup of speech-to-text artifacts using conversation context."""
#     # Apply deterministic fixes first — free, instant, can't change meaning
#     raw_text = _apply_stt_fixes(raw_text)
# 
#     client = _get_client()
# 
#     # Build context from recent exchanges
#     if recent_history:
#         context_lines = []
#         for m in recent_history[-6:]:
#             speaker = "Detective" if m.role == "user" else "Diego"
#             context_lines.append(f"{speaker}: {m.content}")
#         context_section = "Recent conversation for context:\n" + "\n".join(context_lines)
#     else:
#         context_section = ""
# 
#     prompt = CLEANUP_PROMPT_TEMPLATE.format(
#         raw_text=raw_text,
#         context_section=context_section,
#     )
# 
#     try:
#         response = await asyncio.wait_for(
#             client.chat.complete_async(
#                 model=JUDGE_MODEL,
#                 messages=[{"role": "user", "content": prompt}],
#                 temperature=0.0,
#             ),
#             timeout=5,  # Must be fast — blocks the player seeing their text
#         )
#         cleaned = response.choices[0].message.content.strip()
#         # Sanity: if cleanup returned something wildly different in length, keep original
#         if len(cleaned) < len(raw_text) * 0.3 or len(cleaned) > len(raw_text) * 3:
#             return raw_text
#         # Strip quotes if the model wrapped it
#         if cleaned.startswith('"') and cleaned.endswith('"'):
#             cleaned = cleaned[1:-1]
#         return cleaned
#     except Exception:
#         return raw_text  # Fallback to raw on any failure
