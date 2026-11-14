from dataclasses import dataclass


@dataclass(frozen=True)
class Prompt:
    """Declare prompt text and provenance without sending metadata to the model."""

    title: str
    role: str
    text: str
    origin: str
    origin_note: str

    def render(
        self, character: str, ascension: int, game_seed: str | int | None
    ) -> str:
        """Include an optional seed instruction for the agent to enter through the game UI."""
        seed_instruction = (
            f"Enter seed {game_seed} in the game's seed field before starting the run.\n\n"
            if game_seed is not None
            else ""
        )
        return self.text.format(
            character=character,
            ascension=ascension,
            seed_instruction=seed_instruction,
        )


FIRST_COMBAT = Prompt(
    title="first_combat",
    role="subject",
    origin="https://epoch.ai/benchmarks/spireclimb",
    origin_note="Minimal user-requested prompt with character, offline wiki location and optional game-seed instruction; not a verified Epoch prompt.",
    text=(
        "play Slay the Spire for me as {character}\n\n"
        "{seed_instruction}"
        "An offline Slay the Spire wiki is available at /opt/sts/wiki.md."
    ),
)

BEAT_GAME = Prompt(
    title="beat_game",
    role="subject",
    origin="User request, 2026-11-13",
    origin_note="Minimal prompt for the user's requested full-game Ascension 20 attempt, including the offline wiki location and optional game-seed instruction.",
    text=(
        "Try to beat Slay the Spire on Ascension {ascension} as {character}.\n\n"
        "{seed_instruction}"
        "An offline Slay the Spire wiki is available at /opt/sts/wiki.md."
    ),
)

PROMPTS = {prompt.title: prompt for prompt in [FIRST_COMBAT, BEAT_GAME]}
