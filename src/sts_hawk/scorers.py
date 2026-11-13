from inspect_ai.scorer import (
    CORRECT,
    INCORRECT,
    Score,
    Scorer,
    Target,
    accuracy,
    scorer,
)
from inspect_ai.solver import TaskState

from sts_hawk.runtime import observe_game
from sts_hawk.state import wiki_requirement


@scorer(metrics=[accuracy()])
def combat_and_wiki(observer_timeout: int) -> Scorer:
    """Score the actual first-combat result and an earlier enemy wiki read."""

    async def score(state: TaskState, target: Target) -> Score:
        """Require game evidence and tool-boundary evidence for the smoke pass."""
        history = await observe_game(observer_timeout)
        read_enemy = wiki_requirement(history)
        return Score(
            value=CORRECT if history.won and read_enemy else INCORRECT,
            explanation=f"First combat won: {history.won}; enemy wiki read: {read_enemy}; died: {history.died}.",
            metadata=history.model_dump(),
        )

    return score
