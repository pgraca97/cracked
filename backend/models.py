from pydantic import BaseModel, Field
from enum import Enum
from typing import Optional


class Emotion(str, Enum):
    CALM = "calm"
    NERVOUS = "nervous"
    DEFENSIVE = "defensive"
    BREAKING = "breaking"


class DetectiveTone(str, Enum):
    CASUAL = "casual"
    PRESSING = "pressing"
    CONFRONTATIONAL = "confrontational"
    EMPATHETIC = "empathetic"


class Verdict(str, Enum):
    GUILTY = "guilty"
    NOT_GUILTY = "not_guilty"


# What Mistral returns every turn (Diego's response)
# NOTE: contradictions_detected removed - Diego is a suspect, not a referee.
# Contradiction catching is the player's job, validated by the judge.
class DiegoResponse(BaseModel):
    dialogue: str
    emotion: Emotion
    internal_thought: str = ""
    facts_mentioned: list[str] = []
    relationship_pressured: bool = False
    confession: bool = False


# What the judge returns after evaluating a turn
class JudgeResponse(BaseModel):
    facts_extracted: list[str] = []
    contradiction_caught: Optional[str] = None  # "bathroom" | "andre_shift" | "north_corridor" | "backpack" | null
    contradiction_explanation: str = ""
    relationship_pressure: bool = False
    detective_tone: DetectiveTone = DetectiveTone.CASUAL
    player_text_enhanced: str = ""  # punctuation-corrected version of what the detective said


# Conversation turn stored in history
class ChatMessage(BaseModel):
    role: str  # "user" or "assistant"
    content: str


# Full game state, sent alongside each Mistral call
class GameState(BaseModel):
    turn_number: int = 0
    time_elapsed_seconds: float = 0.0
    time_limit_seconds: int = 600
    emotion_state: Emotion = Emotion.CALM
    # dict: trap_name -> explanation (deduplicates by key, values shown in evidence panel)
    contradictions_caught: dict[str, str] = {}
    facts_log: list[str] = []
    # 0-5 scale: how much the player has probed the personal relationship with André
    relationship_pressure: int = 0
    detective_tone: DetectiveTone = DetectiveTone.CASUAL
    confession_triggered: bool = False
    conversation_history: list[ChatMessage] = []


# Final score shown on result screen
class CaseResult(BaseModel):
    verdict: Verdict
    stars: int = Field(ge=0, le=3)
    contradictions: int
    confession: bool
    time_seconds: float
    summary: str
