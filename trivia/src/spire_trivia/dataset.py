"""Select questions and materialize images without exposing answer metadata."""

import base64
import json
from pathlib import Path

from inspect_ai.dataset import MemoryDataset, Sample
from inspect_ai.model import (
    ChatMessageSystem,
    ChatMessageUser,
    ContentImage,
    ContentText,
)

DATA_DIR = Path(__file__).parent / "data"
CATEGORIES = {"cards", "relics", "monsters", "potions", "events", "mechanics"}
KINDS = {
    "description_to_title",
    "title_to_description",
    "number",
    "art_to_title",
    "moves_to_enemy",
    "definition_to_term",
}


def get_trivia_dataset(
    question_set: str,
    game: str | None,
    category: str | None,
    question_kind: str | None,
    include_images: bool,
    sample_ids: list[str] | None,
    smoke: bool,
    system_prompt: str,
) -> MemoryDataset:
    """Compose dataset filters and return independent text or image samples."""
    if question_set not in {
        "text200-v5",
        "text200-v4",
        "text200-v3",
        "text200-v2",
        "text200",
        "text100",
        "all200",
    }:
        raise ValueError(
            "question_set must be text200-v5, text200-v4, text200-v3, text200-v2, text200, text100, or all200"
        )
    suffix = {
        "text200-v5": "-text200-v5",
        "text200-v4": "-text200-v4",
        "text200-v3": "-text200-v3",
        "text200-v2": "-text200-v2",
        "text200": "-text200",
    }.get(question_set, "")
    records = [
        json.loads(line)
        for line in (DATA_DIR / f"participants{suffix}.jsonl").read_text().splitlines()
    ]
    answers = json.loads((DATA_DIR / f"answer-key{suffix}.json").read_text())
    if question_set == "text100":
        selected_ids = set(
            json.loads((DATA_DIR / "text100-selection.json").read_text())[
                "selected_ids"
            ]
        )
        records = [r for r in records if r["id"] in selected_ids]
    records = [r for r in records if include_images or not r["image"]]
    if game is not None and game not in {"sts1", "sts2"}:
        raise ValueError("game must be sts1 or sts2")
    if category is not None and category not in CATEGORIES:
        raise ValueError(f"Unknown category: {category}")
    if question_kind is not None and question_kind not in KINDS:
        raise ValueError(f"Unknown question kind: {question_kind}")
    if sample_ids is not None:
        unknown = set(sample_ids) - {r["id"] for r in records}
        if unknown:
            raise ValueError(f"Unknown sample IDs: {sorted(unknown)}")
    if smoke:
        selected = []
        for g in ["sts1", "sts2"]:
            for c in sorted(CATEGORIES):
                options = [r for r in records if r["game"] == g and r["category"] == c]
                if c == "cards":
                    kind = (
                        "art_to_title" if any(r["image"] for r in options) else "number"
                    )
                    options = [r for r in options if r["kind"] == kind]
                if c == "monsters":
                    options = [r for r in options if r["kind"] == "number"]
                selected.append(options[0]["id"])
        records = [r for r in records if r["id"] in selected]
    records = [
        r
        for r in records
        if (game is None or r["game"] == game)
        and (category is None or r["category"] == category)
        and (question_kind is None or r["kind"] == question_kind)
        and (include_images or not r["image"])
        and (sample_ids is None or r["id"] in sample_ids)
    ]
    if not records:
        raise ValueError("No questions match the selected filters")
    return MemoryDataset(
        [record_to_sample(r, answers[r["id"]], system_prompt) for r in records],
        name="spire-trivia-200",
    )


def record_to_sample(record: dict, answer: str, system_prompt: str) -> Sample:
    """Convert a participant record to one sample with an opaque inline image."""
    content = [ContentText(text=record["input"])]
    if record["image"]:
        image_path = DATA_DIR / record["image"]
        content.append(
            ContentImage(
                image="data:image/png;base64,"
                + base64.b64encode(image_path.read_bytes()).decode()
            )
        )
    return Sample(
        id=record["id"],
        input=[
            ChatMessageSystem(content=system_prompt),
            ChatMessageUser(content=content),
        ],
        target=answer,
        metadata={k: record[k] for k in ["game", "category", "kind"]},
    )
