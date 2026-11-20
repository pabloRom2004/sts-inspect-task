"""Exercise scoring, image transport, independence, filters, and epochs through Inspect."""

import json
import os

import pytest
from inspect_ai import eval as inspect_eval
from inspect_ai.log import read_eval_log
from inspect_ai.model import ContentImage, ModelOutput, get_model
from spire_trivia import trivia
from spire_trivia.dataset import DATA_DIR


def baseline_task(**kwargs):
    """Select the frozen eight-choice protocol explicitly for historical regressions."""
    kwargs.setdefault("question_set", "text200-v2")
    return trivia(system_prompt="knowledge_only", scorer="strict_letter", **kwargs)


@pytest.mark.parametrize(
    "completion,valid",
    [
        ("A", True),
        (" a ", False),
        ("A.", False),
        ("Answer: A", False),
        ("A\nB", False),
        ("", False),
    ],
)
def test_strict_response_format(tmp_path, completion, valid):
    """Reject explanations, lowercase letters, punctuation, and multiple answers."""
    question_id = "sts1-001"
    target = json.loads((DATA_DIR / "answer-key.json").read_text())[question_id]
    response = target if completion == "A" else completion
    model = get_model(
        "mockllm/model",
        custom_outputs=[ModelOutput.from_content("mockllm/model", response)],
    )
    log = inspect_eval(
        baseline_task(question_set="all200", sample_ids=[question_id]),
        model=model,
        log_dir=_log_dir(tmp_path),
        display="none",
    )[0]
    result = read_eval_log(log.location).samples[0]
    assert result.error is None
    assert result.scores["strict_letter"].value == {
        "accuracy": "C" if valid else "I",
        "format": "C" if valid else "I",
    }


def test_wrong_letter_is_valid_but_incorrect(tmp_path):
    """Keep a legitimate wrong answer separate from an invalid response format."""
    target = json.loads((DATA_DIR / "answer-key.json").read_text())["sts1-001"]
    wrong = next(x for x in "ABCDEFGH" if x != target)
    model = get_model(
        "mockllm/model",
        custom_outputs=[ModelOutput.from_content("mockllm/model", wrong)],
    )
    log = inspect_eval(
        baseline_task(question_set="all200", sample_ids=["sts1-001"]),
        model=model,
        log_dir=_log_dir(tmp_path),
        display="none",
    )[0]
    assert log.samples[0].scores["strict_letter"].value == {
        "accuracy": "I",
        "format": "C",
    }


def test_full_dataset_and_smoke_independence(tmp_path):
    """Carry independent text prompts through two Inspect epochs."""
    full = baseline_task()
    assert len(full.dataset) == 200
    assert len(baseline_task(question_set="text100").dataset) == 100
    assert len(baseline_task(question_set="all200", include_images=True).dataset) == 200
    assert (
        len(baseline_task(game="sts2", category="cards", include_images=False).dataset)
        == 50
    )
    task = baseline_task(smoke=True)
    assert len(task.dataset) == 12
    assert {s.metadata["game"] for s in task.dataset} == {"sts1", "sts2"}
    assert len([s for s in task.dataset if s.metadata["kind"] == "art_to_title"]) == 0
    outputs = [ModelOutput.from_content("mockllm/model", "A")] * 24
    log = inspect_eval(
        task,
        model=get_model("mockllm/model", custom_outputs=outputs),
        epochs=2,
        log_dir=_log_dir(tmp_path),
        display="none",
    )[0]
    assert log.status == "success"
    assert len(log.samples) == 24
    assert all(s.error is None for s in log.samples)
    for sample in read_eval_log(log.location).samples:
        assert [m.role for m in sample.messages] == ["system", "user", "assistant"]
        assert not sample.messages[-1].tool_calls
        assert "single uppercase letter" in sample.messages[0].text
        assert not any(isinstance(c, ContentImage) for c in sample.messages[1].content)


def test_invalid_filters_fail_before_inference():
    """Fail loudly on unknown IDs, unknown games, and empty intersections."""
    for kwargs in [
        {"game": "sts3"},
        {"sample_ids": ["missing"]},
        {"category": "unknown"},
        {"category": "events", "question_kind": "art_to_title"},
    ]:
        with pytest.raises(ValueError):
            baseline_task(**kwargs)


def _log_dir(tmp_path):
    """Allow local validation to retain Inspect archives in the workspace log directory."""
    return os.environ.get("SPIRE_TRIVIA_TEST_LOG_DIR", str(tmp_path))


def test_historical_text200_v2_matches_fixed_protocol(tmp_path):
    """Run all two hundred text prompts through real generation and scoring boundaries."""
    task = baseline_task()
    selection = json.loads((DATA_DIR / "text200-v2-protocol.json").read_text())
    assert [s.id for s in task.dataset] == selection["selected_ids"]
    assert len(task.dataset) == 200
    assert all(s.metadata["kind"] != "art_to_title" for s in task.dataset)
    model = get_model(
        "mockllm/model",
        custom_outputs=[
            ModelOutput.from_content("mockllm/model", s.target) for s in task.dataset
        ],
    )
    log = inspect_eval(
        task, model=model, max_samples=1, log_dir=_log_dir(tmp_path), display="none"
    )[0]
    assert log.status == "success" and len(log.samples) == 200
    for sample in read_eval_log(log.location).samples:
        assert sample.error is None
        assert sample.scores["strict_letter"].value == {"accuracy": "C", "format": "C"}
        assert [m.role for m in sample.messages] == ["system", "user", "assistant"]
        assert not any(isinstance(c, ContentImage) for c in sample.messages[1].content)


def test_archived_image_question_remains_explicit(tmp_path):
    """Keep the original image protocol available only through explicit archive settings."""
    task = baseline_task(
        question_set="all200", include_images=True, sample_ids=["sts1-041"]
    )
    model = get_model(
        "mockllm/model",
        custom_outputs=[
            ModelOutput.from_content("mockllm/model", task.dataset[0].target)
        ],
    )
    log = inspect_eval(task, model=model, log_dir=_log_dir(tmp_path), display="none")[0]
    sample = read_eval_log(log.location).samples[0]
    assert (
        sample.error is None and sample.scores["strict_letter"].value["accuracy"] == "C"
    )
    assert any(isinstance(c, ContentImage) for c in sample.messages[1].content)


def test_replacement_preserves_historical_question_and_other_inputs():
    """Keep the retired Block sample reproducible and change only one current sample."""
    previous = {s.id: s for s in baseline_task(question_set="text200").dataset}
    current = {s.id: s for s in baseline_task().dataset}
    assert set(previous) - set(current) == {"sts1-096"}
    assert set(current) - set(previous) == {"sts1-111"}
    assert "Until next turn, prevents damage." in previous["sts1-096"].input[1].text
    assert (
        "Which buff negates the next debuff applied to its bearer?"
        in current["sts1-111"].input[1].text
    )
    assert current["sts1-111"].target == "E"
    assert "E. Artifact" in current["sts1-111"].input[1].text
    for sample_id in set(previous) & set(current):
        assert previous[sample_id].target == current[sample_id].target
        assert previous[sample_id].metadata == current[sample_id].metadata
        assert [(m.role, m.text) for m in previous[sample_id].input] == [
            (m.role, m.text) for m in current[sample_id].input
        ]
