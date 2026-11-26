"""Score answer accuracy separately from the required one-letter format."""

import re

from inspect_ai.scorer import (
    CORRECT,
    INCORRECT,
    Score,
    Scorer,
    Target,
    accuracy,
    mean,
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


def final_choice(completion: str) -> str:
    """Accept one uppercase choice on the last nonempty line of the final message."""
    lines = completion.strip().splitlines()
    last = lines[-1].strip() if lines else ""
    return last if re.fullmatch("[A-I]", last) else ""


@scorer(
    metrics={
        "net_score": [mean(), stderr()],
        "accuracy": [accuracy()],
        "abstention": [accuracy()],
        "format": [accuracy()],
    }
)
def abstention_letter(recover_final: bool = False) -> Scorer:
    """Award +1 for a correct choice, 0 for I, and -1 for a wrong or malformed response."""

    async def score(state: TaskState, target: Target) -> Score:
        """Keep abstention distinct from errors while grading the complete final response."""
        answer = state.output.completion.strip()
        exact = re.fullmatch("[A-I]", answer) is not None
        choice = final_choice(answer) if recover_final else answer
        valid = re.fullmatch("[A-I]", choice) is not None
        correct = valid and choice == target.text
        abstained = choice == "I"
        outcome = (
            "correct"
            if correct
            else "abstained"
            if abstained
            else "wrong"
            if valid
            else "invalid"
        )
        return Score(
            value={
                "net_score": 1 if correct else 0 if abstained else -1,
                "accuracy": CORRECT if correct else INCORRECT,
                "abstention": CORRECT if abstained else INCORRECT,
                "format": CORRECT if exact else INCORRECT,
            },
            answer=answer,
            explanation={
                "correct": "Correct choice (+1).",
                "abstained": "Explicit I don't know (0).",
                "wrong": "Incorrect choice (-1).",
                "invalid": "Response is not exactly one uppercase A–I letter (-1).",
            }[outcome],
            metadata={"outcome": outcome, "choice": choice if valid else None},
        )

    return score


SCORERS = {"strict_letter": strict_letter, "abstention_letter": abstention_letter}
