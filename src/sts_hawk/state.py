import re
from typing import Any

from inspect_ai.util import StoreModel
from pydantic import BaseModel, Field


class WikiRead(BaseModel):
    """Record the article actually returned at a wiki tool boundary."""

    title: str
    before_victory: bool
    enemies_present: list[str]


class RunState(StoreModel):
    """Persist observations and wiki reads independently of model context."""

    observations: int = 0
    first_enemies: list[str] = Field(default_factory=list)
    won: bool = False
    died: bool = False
    wiki_reads: list[WikiRead] = Field(default_factory=list)


def observe(raw: dict[str, Any], history: RunState) -> None:
    """Update trusted first-combat evidence from CommunicationMod state."""
    if raw.get("error"):
        raise RuntimeError(f"Game observer failed: {raw['error']}")
    if "in_game" not in raw:
        raise ValueError("Observer response lacks in_game")
    game = raw.get("game_state", {})
    history.observations += 1
    if not raw["in_game"]:
        return
    if "floor" not in game or "current_hp" not in game:
        raise ValueError("In-game observer response lacks floor or health")
    floor = game["floor"]
    if floor == 1 and game.get("combat_state", {}).get("monsters"):
        names = [m["name"] for m in game["combat_state"]["monsters"]]
        if not history.first_enemies:
            history.first_enemies = names
    screen = game.get("screen_type", raw.get("screen_type"))
    if game["current_hp"] <= 0 or screen == "DEATH":
        history.died = True
    if floor == 1 and screen == "COMBAT_REWARD" and game["current_hp"] > 0:
        if not history.first_enemies:
            raise RuntimeError(
                "Victory observed without the first combat being observed"
            )
        history.won = True
    if floor > 1 and not history.won:
        raise RuntimeError("Passed the first floor without observing its combat result")


def enemy_article(enemy: str) -> str:
    """Map game enemy labels to titles in the copied wiki."""
    compact = re.sub(r"[^a-z]", "", enemy.lower())
    if "louse" in compact:
        return "louses"
    if "acidslime" in compact:
        return "acidslime"
    if "spikeslime" in compact:
        return "spikeslime"
    return compact


def wiki_requirement(history: RunState) -> bool:
    """Check that a first-combat enemy article was read before victory."""
    expected = {enemy_article(enemy) for enemy in history.first_enemies}
    return any(
        read.before_victory
        and bool(read.enemies_present)
        and re.sub(r"[^a-z]", "", read.title.lower()) in expected
        for read in history.wiki_reads
    )
