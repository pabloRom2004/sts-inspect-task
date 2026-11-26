"""Compose a one-generation trivia task without tools or a game sandbox."""

from typing import cast

from inspect_ai import Epochs, Task, task
from inspect_ai.model import GenerateConfig
from inspect_ai.solver import Solver
from inspect_ai.util import registry_create

from spire_trivia.dataset import get_trivia_dataset
from spire_trivia.prompts import SYSTEM_MESSAGES
from spire_trivia.run_config import DEFAULT_ARGS, DEFAULT_CONFIG
from spire_trivia.scorers import SCORERS


@task
def trivia(
    question_set: str = DEFAULT_ARGS["question_set"],
    game: str | None = DEFAULT_ARGS["game"],
    category: str | None = DEFAULT_ARGS["category"],
    question_kind: str | None = DEFAULT_ARGS["question_kind"],
    include_images: bool = DEFAULT_ARGS["include_images"],
    sample_ids: list[str] | None = DEFAULT_ARGS["sample_ids"],
    smoke: bool = DEFAULT_ARGS["smoke"],
    system_prompt: str = DEFAULT_ARGS["system_prompt"],
    scorer: str = DEFAULT_ARGS["scorer"],
) -> Task:
    """Test independent factual questions using one tool-free model turn."""
    if system_prompt not in SYSTEM_MESSAGES:
        raise ValueError(f"Unknown system prompt: {system_prompt}")
    if scorer not in SCORERS:
        raise ValueError(f"Unknown scorer: {scorer}")
    abstention_prompts = {
        "text200-v3": "knowledge_abstention",
        "text200-v4": "knowledge_abstention_explicit",
        "text200-v5": "knowledge_abstention_explicit",
        "text200-v7": "knowledge_abstention_explicit",
        "text200-v6": "knowledge_abstention_explicit",
    }
    expected_prompt = abstention_prompts.get(question_set, "knowledge_only")
    expected_scorer = (
        "abstention_letter" if question_set in abstention_prompts else "strict_letter"
    )
    if system_prompt != expected_prompt or scorer != expected_scorer:
        raise ValueError(
            f"{question_set} requires {expected_prompt} and {expected_scorer}"
        )
    solver = DEFAULT_CONFIG["solver"]
    settings = DEFAULT_CONFIG["eval_config"]
    return Task(
        dataset=get_trivia_dataset(
            question_set,
            game,
            category,
            question_kind,
            include_images,
            sample_ids,
            smoke,
            SYSTEM_MESSAGES[system_prompt],
        ),
        solver=cast(
            Solver, registry_create("solver", solver["solver"], **solver["args"])
        ),
        scorer=SCORERS[scorer](recover_final=True)
        if question_set == "text200-v7"
        else SCORERS[scorer](),
        config=GenerateConfig(**DEFAULT_CONFIG["generate_config"]),
        epochs=Epochs(settings["epochs"], settings["epochs_reducer"]),
        token_limit=settings["token_limit"],
        time_limit=settings["time_limit"],
        message_limit=settings["message_limit"],
        version="0.8.0" if question_set == "text200-v7" else "0.7.1",
        metadata={
            "dataset_revision": "2026-11-26"
            if question_set == "text200-v7"
            else "2026-11-20"
            if question_set in {"text200-v4", "text200-v5", "text200-v6"}
            else "2026-11-19",
            "question_set": question_set,
            "single_turn": True,
            "tools": False,
        },
    )
