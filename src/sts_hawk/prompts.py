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
        "Defeat the Heart to win.\n\n"
        "Play one round and do not restart the game. Play until victory or defeat.\n\n"
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
        "Defeat the Heart to win.\n\n"
        "Play one round and do not restart the game. Play until victory or defeat.\n\n"
        "{seed_instruction}"
        "An offline Slay the Spire wiki is available at /opt/sts/wiki.md."
    ),
)

BEAT_GAME_STS2 = Prompt(
    title="beat_game_sts2",
    role="subject",
    origin="User request, 2026-11-16",
    origin_note="Minimal StS2 prompt for the purchased v0.107.1 Linux copy; no offline StS2 wiki is supplied yet.",
    text=(
        "Try to beat Slay the Spire 2 on Ascension {ascension} as {character}.\n\n"
        "The game can take about a minute to load. "
        "Wait for loading to finish before continuing.\n\n"
        "Complete all three Acts to win.\n\n"
        "Play one round and do not restart the game. Play until victory or defeat.\n\n"
        "{seed_instruction}"
    ),
)

FIRST_COMBAT_SMOKE = Prompt(
    title="first_combat_smoke",
    role="subject",
    origin="User request, 2026-11-16",
    origin_note="Bounded StS1 integration check requiring an enemy wiki lookup, one combat and an integer submission; not a performance benchmark prompt.",
    text=(
        "Play Slay the Spire on Ascension {ascension} as {character}.\n\n"
        "Read the offline wiki about the first enemy you encounter. "
        "Play the first combat, then stop and call submit with the maximum floor "
        "reached as an integer. If you lose, stop and submit.\n\n"
        "Play one round and do not restart the game.\n\n"
        "{seed_instruction}"
        "An offline Slay the Spire wiki is available at /opt/sts/wiki.md."
    ),
)

FIRST_COMBAT_SMOKE_STS2 = Prompt(
    title="first_combat_smoke_sts2",
    role="subject",
    origin="User request, 2026-11-16",
    origin_note="StS2 integration smoke stopping after one combat; no offline StS2 wiki supplied.",
    text=(
        "Play Slay the Spire 2 on Ascension {ascension} as {character}.\n\n"
        "The game can take about a minute to load. "
        "Wait for loading to finish before continuing.\n\n"
        "Play the first combat, then stop and call submit with the maximum floor "
        "reached as an integer. If you lose, stop and submit.\n\n"
        "Play one round and do not restart the game.\n\n"
        "{seed_instruction}"
    ),
)

PROMPTS = {
    prompt.title: prompt
    for prompt in [
        FIRST_COMBAT,
        BEAT_GAME,
        BEAT_GAME_STS2,
        FIRST_COMBAT_SMOKE,
        FIRST_COMBAT_SMOKE_STS2,
    ]
}
