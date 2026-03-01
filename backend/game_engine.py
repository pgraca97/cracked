from models import GameState, DiegoResponse, JudgeResponse, ChatMessage, CaseResult, Emotion, Verdict
import ai_client


EMOTION_THRESHOLDS = {
    0: Emotion.CALM,
    1: Emotion.NERVOUS,
    2: Emotion.DEFENSIVE,
}
# 3+ → BREAKING

# Numeric severity for comparing emotions (string .value comparison won't work)
_EMOTION_RANK = {
    Emotion.CALM: 0,
    Emotion.NERVOUS: 1,
    Emotion.DEFENSIVE: 2,
    Emotion.BREAKING: 3,
}


def _emotion_for_contradictions(count: int) -> Emotion:
    return EMOTION_THRESHOLDS.get(count, Emotion.BREAKING)


def _normalize(text: str) -> set[str]:
    """Reduce a fact to a bag of lowercase keywords for fuzzy comparison."""
    stopwords = {"he", "was", "at", "the", "a", "an", "in", "on", "to", "his", "for", "of", "per", "diego", "claims", "says", "states"}
    words = set(text.lower().split())
    return words - stopwords


def _is_duplicate_fact(new_fact: str, existing: list[str]) -> bool:
    """True if new_fact overlaps heavily with any existing fact."""
    new_words = _normalize(new_fact)
    if len(new_words) < 2:
        return False
    for old in existing:
        old_words = _normalize(old)
        if not old_words:
            continue
        overlap = new_words & old_words
        # If 70%+ of the new fact's keywords already appear in an existing fact, skip it
        if len(overlap) / len(new_words) >= 0.7:
            return True
    return False


class GameEngine:
    def __init__(self):
        self._state = GameState()

    @property
    def state(self) -> GameState:
        return self._state

    async def process_turn(self, player_text: str, time_elapsed: float) -> tuple[DiegoResponse, str]:
        """Returns (diego_response, enhanced_player_text)."""
        self._state.turn_number += 1
        self._state.time_elapsed_seconds = time_elapsed

        # 1. Get Diego's response
        response = await ai_client.chat(self._state, player_text)

        # 2. Judge evaluates the turn (facts, contradictions, relationship)
        judge = await ai_client.judge_turn(
            self._state.facts_log,
            self._state.conversation_history,
            player_text,
            response,
        )

        # 3. Update game state from both Diego and the judge
        self._update_state(response, judge)

        # 4. Append to conversation history after state update
        # Use enhanced text (with restored punctuation) so Diego sees intended intensity on future turns
        enhanced = judge.player_text_enhanced or player_text
        self._state.conversation_history.append(
            ChatMessage(role="user", content=enhanced)
        )
        self._state.conversation_history.append(
            ChatMessage(role="assistant", content=response.dialogue)
        )

        return response, enhanced

    def _update_state(self, response: DiegoResponse, judge: JudgeResponse):
        # Facts: use the judge's extraction, skip near-duplicates
        for fact in judge.facts_extracted:
            if not _is_duplicate_fact(fact, self._state.facts_log):
                self._state.facts_log.append(fact)

        # Contradictions: only from the judge, deduplicated by trap name
        if judge.contradiction_caught and judge.contradiction_caught not in self._state.contradictions_caught:
            self._state.contradictions_caught[judge.contradiction_caught] = judge.contradiction_explanation

        # Relationship pressure: increment (0-5 scale) when the judge detects personal probing
        if judge.relationship_pressure and self._state.relationship_pressure < 5:
            self._state.relationship_pressure += 1

        # Confession: only from Diego's own response (he decides when to break)
        if response.confession:
            self._state.confession_triggered = True

        # Detective tone: store for Diego's next response
        self._state.detective_tone = judge.detective_tone

        # Recalculate emotion from contradiction count
        n = len(self._state.contradictions_caught)
        self._state.emotion_state = _emotion_for_contradictions(n)

        # Relationship pressure accelerates emotion when it's high enough
        # If relationship_pressure >= 3 and at least 1 contradiction, bump to at least defensive
        if self._state.relationship_pressure >= 3 and n >= 1:
            if _EMOTION_RANK[self._state.emotion_state] < _EMOTION_RANK[Emotion.DEFENSIVE]:
                self._state.emotion_state = Emotion.DEFENSIVE

        # If 2+ contradictions AND high relationship pressure, force breaking
        if n >= 2 and self._state.relationship_pressure >= 3:
            self._state.emotion_state = Emotion.BREAKING

    def calculate_result(self, verdict: Verdict, time_elapsed: float) -> CaseResult:
        n = len(self._state.contradictions_caught)
        confession = self._state.confession_triggered

        if verdict == Verdict.NOT_GUILTY:
            return CaseResult(
                verdict=verdict,
                stars=0,
                contradictions=n,
                confession=confession,
                time_seconds=time_elapsed,
                summary="Diego Fonseca was released. The diamond was never found.",
            )

        # Guilty verdicts
        if confession:
            return CaseResult(
                verdict=verdict,
                stars=3,
                contradictions=n,
                confession=confession,
                time_seconds=time_elapsed,
                summary="Diego Fonseca confessed. The diamond was recovered.",
            )
        elif n >= 3:
            return CaseResult(
                verdict=verdict,
                stars=3,
                contradictions=n,
                confession=confession,
                time_seconds=time_elapsed,
                summary="Overwhelming evidence. Diego Fonseca was convicted.",
            )
        elif n == 2:
            return CaseResult(
                verdict=verdict,
                stars=2,
                contradictions=n,
                confession=confession,
                time_seconds=time_elapsed,
                summary="Enough evidence to prosecute, but no confession.",
            )
        else:
            return CaseResult(
                verdict=verdict,
                stars=1,
                contradictions=n,
                confession=confession,
                time_seconds=time_elapsed,
                summary="You got the right guy, but the evidence won't hold in court.",
            )
