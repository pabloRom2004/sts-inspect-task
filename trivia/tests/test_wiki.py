"""Guard the user-reported ambiguity and cross-game novelty regressions."""

import json

from spire_trivia import trivia
from spire_trivia.dataset import DATA_DIR


def test_wiki_revision_and_numeric_focus():
    task = trivia()
    assert task.metadata["question_set"] == "text200-v6"
    assert len(task.dataset) == 200
    for game in ["sts1", "sts2"]:
        samples = [s for s in task.dataset if s.metadata["game"] == game]
        assert len(samples) == 100
        assert sum(s.metadata["kind"] == "number" for s in samples) == 55
        assert not any(s.metadata["kind"] == "moves_to_enemy" for s in samples)
        assert all(s.input[1].text.endswith("I. I don't know") for s in samples)
    protocol = json.loads((DATA_DIR / "text200-v5-protocol.json").read_text())
    assert protocol["gold_plated_cables_unchanged"]
    audit = json.loads((DATA_DIR / "sts2-wiki-novelty-audit.json").read_text())
    assert len(audit["questions"]) == 100
    for q in audit["questions"]:
        assert q["target"]["wiki_revision_id"] > 0
        assert "slaythespire.wiki.gg/index.php?" in q["target"]["url"]
        assert q["novelty_basis"]
        assert q["target"]["entity_name"] not in ["Eternal", "One-Two Punch", "Hotfix"]
    names = {q["target"]["entity_name"] for q in audit["questions"]}
    for name in [
        "Hellraiser",
        "Knife Trap",
        "Fan of Knives",
        "Focused Strike",
        "Tesla Coil",
    ]:
        assert name in names


def test_preserve_precise_relic_effect():
    old = trivia(
        question_set="text200-v4",
        system_prompt="knowledge_abstention_explicit",
        scorer="abstention_letter",
    )
    previous = next(s for s in old.dataset if s.id == "sts1-058")
    current = next(s for s in trivia().dataset if s.id == "sts1-058")
    assert [m.text for m in current.input] == [
        m.text for m in previous.input
    ] and current.target == previous.target


def test_slaver_variant_is_explicit():
    sample = next(s for s in trivia().dataset if s.id == "sts1-239")
    assert "Blue Slaver" in sample.input[1].text
    assert not any(s.id == "sts1-228" for s in trivia().dataset)
    old = trivia(
        question_set="text200-v5",
        system_prompt="knowledge_abstention_explicit",
        scorer="abstention_letter",
    )
    previous = {s.id: s for s in old.dataset}
    assert all(
        [m.text for m in s.input] == [m.text for m in previous[s.id].input]
        and s.target == previous[s.id].target
        for s in trivia().dataset
        if s.id != "sts1-239"
    )
