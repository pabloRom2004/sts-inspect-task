"""Check the new-content bank, exact scoring instruction and historical separation."""

import json
import os

from inspect_ai import eval as inspect_eval
from inspect_ai.log import read_eval_log
from inspect_ai.model import ContentImage, ModelOutput, get_model
from spire_trivia import trivia
from spire_trivia.dataset import DATA_DIR

SCORING = "A correct answer scores +1, an incorrect answer scores −1, and I don’t know scores 0."


def novel_task(**kwargs):
    """Select the v4 bank and its explicitly named scoring prompt."""
    return trivia(
        question_set="text200-v4",
        system_prompt="knowledge_abstention_explicit",
        scorer="abstention_letter",
        **kwargs,
    )


def test_novel_content_and_exact_prompt():
    """Keep StS1 question bodies unchanged and every StS2 entity absent from StS1."""
    old = trivia(
        question_set="text200-v3",
        system_prompt="knowledge_abstention",
        scorer="abstention_letter",
    )
    previous = {s.id: s for s in old.dataset}
    new = novel_task()
    assert len(new.dataset) == 200
    for s in new.dataset:
        prompt = s.input[0].text
        assert (
            SCORING in prompt
            and "more likely" not in prompt
            and "guess" not in prompt
            and "confidence" not in prompt
        )
        assert s.input[1].text.endswith("I. I don't know")
        if s.metadata["game"] == "sts1":
            assert (
                s.input[1].text == previous[s.id].input[1].text
                and s.target == previous[s.id].target
            )
        else:
            assert s.id not in previous
    audit = json.loads((DATA_DIR / "sts2-novelty-audit.json").read_text())
    keys = set(audit["sts1_keys"])
    import re

    for q in audit["questions"]:
        for e in q["choice_entities"]:
            assert re.sub("[^a-z0-9]", "", e["name"].lower()) not in keys
            assert re.sub("[^a-z0-9]", "", e["id"].lower()) not in keys
    assert len(audit["questions"]) == 100
    assert len(novel_task(game="sts2", smoke=True).dataset) == 6


def test_novel_full_mock_round_trip(tmp_path):
    """Exercise every new input with correct, abstained and wrong scripted outcomes."""
    task = trivia()
    outputs = []
    wanted = {}
    for i, s in enumerate(task.dataset):
        answer = (
            s.target
            if i % 3 == 0
            else "I"
            if i % 3 == 1
            else next(x for x in "ABCDEFGH" if x != s.target)
        )
        points = 1 if i % 3 == 0 else 0 if i % 3 == 1 else -1
        outputs.append(ModelOutput.from_content("mockllm/model", answer))
        wanted[s.id] = points
    log = inspect_eval(
        task,
        model=get_model("mockllm/model", custom_outputs=outputs),
        max_samples=1,
        log_dir=os.environ.get("SPIRE_TRIVIA_TEST_LOG_DIR", str(tmp_path)),
        display="none",
    )[0]
    result = read_eval_log(log.location)
    assert result.status == "success" and len(result.samples) == 200
    assert result.plan.config.reasoning_effort == "medium"
    assert all(
        e.config.reasoning_effort == "medium"
        for s in result.samples
        for e in s.events
        if e.event == "model"
    )
    for s in result.samples:
        assert s.error is None and s.limit is None
        assert s.scores["abstention_letter"].value["net_score"] == wanted[s.id]
        assert [m.role for m in s.messages] == ["system", "user", "assistant"]
        assert not any(isinstance(c, ContentImage) for c in s.messages[1].content)
