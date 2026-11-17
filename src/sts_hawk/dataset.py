"""Build stable game samples from the selected prompt contract."""

from inspect_ai.dataset import Sample
from inspect_ai.model import ChatMessageSystem, ChatMessageUser

from sts_hawk.prompts import Prompt


def get_sts_dataset(
    prompt: Prompt, character: str, ascension: int, game_seed: str | int | None
) -> list[Sample]:
    """Render one seeded game while preserving separate system and user message roles."""
    if prompt.system_text is not None and game_seed is None:
        raise ValueError("The replay-based task requires an explicit game seed.")
    user_input = prompt.render(
        character=character.title(), ascension=ascension, game_seed=game_seed
    )
    return [
        Sample(
            id=f"{character.lower()}-a{ascension}-{prompt.title.replace('_', '-')}"
            + (f"-seed-{game_seed}" if game_seed is not None else ""),
            input=[
                ChatMessageSystem(content=prompt.system_text),
                ChatMessageUser(content=user_input),
            ]
            if prompt.system_text is not None
            else user_input,
            metadata={
                "requested_game_seed": game_seed,
                "epoch_prompt": prompt.system_text is not None,
                "desktop_height": 720,
            },
        )
    ]
