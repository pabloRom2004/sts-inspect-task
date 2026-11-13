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
    origin_note="Exact minimal prompt requested by the user on 2026-11-13; not a verified Epoch prompt.",
    text="play Slay the Spire for me",
)

PROMPTS = {FIRST_COMBAT.title: FIRST_COMBAT}
