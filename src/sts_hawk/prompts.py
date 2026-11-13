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
    origin_note="New smoke prompt inspired by the published methodology; not Epoch's unreleased prompt.",
    text="""Play Slay the Spire through its graphical interface. You are {character} at Ascension {ascension}.
Use computer screenshots and graphical actions to play. Start by taking a screenshot.
Choose your starting bonus and enter the first combat. Identify the enemy or enemies from the screen, then use wiki to read the relevant enemy article before fighting.
The wiki tool reads an offline copy of the Slay the Spire wiki. A title query returns an article; a broader query returns matching titles.
Defeat that first encounter, then stop. Do not begin a second combat. The harness also stops automatically when it detects the first combat victory or your death.
If an animation is still running, use computer's wait action and inspect the next screenshot.
Report briefly whether you defeated the encounter and which wiki article you consulted.""",
)

PROMPTS = {FIRST_COMBAT.title: FIRST_COMBAT}
