from dataclasses import dataclass


@dataclass(frozen=True)
class Prompt:
    """Declare prompt text and provenance without sending metadata to the model."""

    title: str
    role: str
    text: str
    origin: str
    origin_note: str


FIRST_COMBAT = Prompt(
    title="first_combat",
    role="subject",
    origin="https://epoch.ai/benchmarks/spireclimb",
    origin_note="Minimal user-requested prompt with character parameter added on 2026-11-13; not a verified Epoch prompt.",
    text="play Slay the Spire for me as {character}",
)

BEAT_GAME = Prompt(
    title="beat_game",
    role="subject",
    origin="User request, 2026-11-13",
    origin_note="Minimal prompt for the user's requested full-game Ascension 20 attempt.",
    text="Try to beat Slay the Spire on Ascension {ascension} as {character}.",
)

PROMPTS = {prompt.title: prompt for prompt in [FIRST_COMBAT, BEAT_GAME]}
