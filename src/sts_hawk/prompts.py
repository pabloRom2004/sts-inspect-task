from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class Prompt:
    """Declare prompt text and provenance without sending metadata to the model."""

    title: str
    role: str
    text: str
    origin: str
    origin_note: str
    system_text: str | None = None
    seed_instruction: str = (
        "Enter seed {game_seed} in the game's seed field before starting the run.\n\n"
    )

    def render(
        self, character: str, ascension: int, game_seed: str | int | None
    ) -> str:
        """Include an optional seed instruction for the agent to enter through the game UI."""
        seed_instruction = (
            self.seed_instruction.format(game_seed=game_seed)
            if game_seed is not None
            else ""
        )
        return self.text.format(
            character=character,
            ascension=ascension,
            seed_instruction=seed_instruction,
            game_seed=game_seed,
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

STS2_SEED_INSTRUCTION = (
    "Choose Singleplayer > Custom. Enter seed {game_seed} in the Seed box "
    "before starting the run. Leave all modifiers off.\n\n"
)


BEAT_GAME_STS2 = Prompt(
    title="beat_game_sts2",
    role="subject",
    origin="User request, 2026-11-16",
    origin_note="Minimal StS2 prompt for the purchased v0.107.1 Linux copy; no offline StS2 wiki is supplied yet.",
    seed_instruction=STS2_SEED_INSTRUCTION,
    text=(
        "Try to beat Slay the Spire 2 on Ascension {ascension} as {character}.\n\n"
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
    seed_instruction=STS2_SEED_INSTRUCTION,
    text=(
        "Play Slay the Spire 2 on Ascension {ascension} as {character}.\n\n"
        "Play the first combat, then stop and call submit with the maximum floor "
        "reached as an integer. If you lose, stop and submit.\n\n"
        "Play one round and do not restart the game.\n\n"
        "{seed_instruction}"
    ),
)

EPOCH_ASSETS = Path(__file__).parent / "assets/epoch"

EPOCH_STS1 = Prompt(
    title="epoch_sts1",
    role="subject",
    origin="Supplied Epoch replay: sts_play_seed13_a20_heart_defect, 2026-11-05",
    origin_note="Captured StS1 system/user messages, parameterized only for character, ascension and seed; integer reporting remains a task tool contract.",
    system_text=(EPOCH_ASSETS / "sts1-system.txt").read_text(),
    text=(EPOCH_ASSETS / "sts1-user.txt").read_text(),
)

EPOCH_STS2 = Prompt(
    title="epoch_sts2",
    role="subject",
    origin="Supplied Epoch replay: sts_play_seed9_a10_ironclad, 2026-09-22",
    origin_note="Captured StS2 system prompt; user message replaces the pre-started run with model-controlled Custom seed entry, as requested.",
    system_text=(EPOCH_ASSETS / "sts2-system.txt").read_text(),
    text=(EPOCH_ASSETS / "sts2-user.txt").read_text(),
)

EPOCH_FIRST_COMBAT_SMOKE = Prompt(
    title="epoch_first_combat_smoke",
    role="subject",
    origin="User-requested replay-profile integration smoke, 2026-11-17",
    origin_note="Original StS1 messages with an explicit first-combat stopping override and required wiki lookup; this is not a performance benchmark prompt.",
    system_text=EPOCH_STS1.system_text,
    text=EPOCH_STS1.text
    + (
        "\n\nSmoke test override: before acting in the first combat, use wiki_search "
        "and wiki_fetch to read about the first enemy you encounter. Play that "
        "combat, then stop immediately when it ends, whether you win or die, "
        "and call submit with the maximum floor reached as an integer. "
        "Do not enter a second combat. This stopping rule overrides the full-game "
        "and Heart objective for this integration smoke only."
    ),
)

EPOCH_FIRST_COMBAT_SMOKE_STS2 = Prompt(
    title="epoch_first_combat_smoke_sts2",
    role="subject",
    origin="User-requested replay-profile StS2 smoke, 2026-11-17",
    origin_note="Captured StS2 system and model-controlled Custom setup, with a first-combat stopping override; not a performance benchmark prompt.",
    system_text=EPOCH_STS2.system_text,
    text=EPOCH_STS2.text
    + (
        "\n\nSmoke test override: play the first combat, then stop immediately "
        "when it ends, whether you win or die, and call submit with the maximum "
        "floor reached as an integer. Do not enter a second combat. This "
        "stopping rule overrides the full-game objective for this smoke only."
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
        EPOCH_STS1,
        EPOCH_STS2,
        EPOCH_FIRST_COMBAT_SMOKE,
        EPOCH_FIRST_COMBAT_SMOKE_STS2,
    ]
}
