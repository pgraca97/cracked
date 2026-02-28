from pydantic import BaseModel, Field
from enum import Enum
from typing import Optional


class Emotion(str, Enum):
    CALM = "calm"
    NERVOUS = "nervous"
    DEFENSIVE = "defensive"
    BREAKING = "breaking"


class Verdict(str, Enum):
    GUILTY = "guilty"
    NOT_GUILTY = "not_guilty"


# What Mistral returns every turn
class DiegoResponse(BaseModel):
    dialogue: str
    emotion: Emotion
    internal_thought: str = ""
    facts_mentioned: list[str] = []
    contradictions_detected: list[str] = []
    relationship_pressured: bool = False
    confession: bool = False


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
    contradictions_caught: list[str] = []
    facts_log: list[str] = []
    relationship_mentioned: bool = False
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
