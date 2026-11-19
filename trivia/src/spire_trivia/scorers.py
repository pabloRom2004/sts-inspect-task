"""Score answer accuracy separately from the required one-letter format."""

import re

from inspect_ai.scorer import (
    CORRECT,
    INCORRECT,
    Score,
    Scorer,
    Target,
    accuracy,
    scorer,
    stderr,
)
from inspect_ai.solver import TaskState


@scorer(metrics={"accuracy": [accuracy(), stderr()], "format": [accuracy()]})
def strict_letter() -> Scorer:
    """Accept exactly one uppercase A–H letter with optional surrounding whitespace."""

    async def score(state: TaskState, target: Target) -> Score:
        """Grade the final completion without extracting answers from explanations."""
        answer = state.output.completion.strip()
        valid = re.fullmatch("[A-H]", answer) is not None
        correct = valid and answer == target.text
        return Score(
            value={
                "accuracy": CORRECT if correct else INCORRECT,
                "format": CORRECT if valid else INCORRECT,
            },
            answer=answer,
            explanation="Exact one-letter match."
            if correct
            else (
                "Incorrect choice."
                if valid
                else "Response is not exactly one uppercase A–H letter."
            ),
        )

    return score


SCORERS = {"strict_letter": strict_letter}
