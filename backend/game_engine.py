from models import GameState, DiegoResponse, ChatMessage, CaseResult, Emotion, Verdict
import ai_client


EMOTION_THRESHOLDS = {
    0: Emotion.CALM,
    1: Emotion.NERVOUS,
    2: Emotion.DEFENSIVE,
}
# 3+ → BREAKING


def _emotion_for_contradictions(count: int) -> Emotion:
    return EMOTION_THRESHOLDS.get(count, Emotion.BREAKING)


class GameEngine:
    def __init__(self):
        self._state = GameState()

    @property
    def state(self) -> GameState:
        return self._state

    async def process_turn(self, player_text: str, time_elapsed: float) -> DiegoResponse:
        self._state.turn_number += 1
        self._state.time_elapsed_seconds = time_elapsed

        response = await ai_client.chat(self._state, player_text)

        self._update_state(response)

        # Append to conversation history after state update
        self._state.conversation_history.append(
            ChatMessage(role="user", content=player_text)
        )
        self._state.conversation_history.append(
            ChatMessage(role="assistant", content=response.dialogue)
        )

        return response

    def _update_state(self, response: DiegoResponse):
        # Accumulate facts
        self._state.facts_log.extend(response.facts_mentioned)

        # Accumulate contradictions (deduplicate)
        for c in response.contradictions_detected:
            if c not in self._state.contradictions_caught:
                self._state.contradictions_caught.append(c)

        # Relationship lever
        if response.relationship_pressured:
            self._state.relationship_mentioned = True

        # Confession flag
        if response.confession:
            self._state.confession_triggered = True

        # Recalculate emotion from contradiction count
        n = len(self._state.contradictions_caught)
        self._state.emotion_state = _emotion_for_contradictions(n)

        # Check confession trigger: 3+ contradictions OR 2+ with relationship pressure
        if n >= 3 or (n >= 2 and self._state.relationship_mentioned):
            # Don't force confession — just make sure Diego is in breaking state
            # so Mistral sees the right emotion and can confess naturally
            if self._state.emotion_state != Emotion.BREAKING:
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
        if n >= 3 or confession:
            return CaseResult(
                verdict=verdict,
                stars=3,
                contradictions=n,
                confession=confession,
                time_seconds=time_elapsed,
                summary="Diego Fonseca confessed. The diamond was recovered.",
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
