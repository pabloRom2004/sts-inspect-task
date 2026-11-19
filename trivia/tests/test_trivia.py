"""Exercise scoring, image transport, independence, filters, and epochs through Inspect."""

import json
import os

import pytest
from inspect_ai import eval as inspect_eval
from inspect_ai.log import read_eval_log
from inspect_ai.model import ContentImage, ModelOutput, get_model
from spire_trivia import trivia
from spire_trivia.dataset import DATA_DIR


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
        trivia(question_set="all200", sample_ids=[question_id]),
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
        trivia(question_set="all200", sample_ids=["sts1-001"]),
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
    full = trivia()
    assert len(full.dataset) == 100
    assert len(trivia(question_set="all200", include_images=True).dataset) == 200
    assert (
        len(trivia(game="sts2", category="cards", include_images=False).dataset) == 24
    )
    task = trivia(smoke=True)
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
            trivia(**kwargs)


def _log_dir(tmp_path):
    """Allow local validation to retain Inspect archives in the workspace log directory."""
    return os.environ.get("SPIRE_TRIVIA_TEST_LOG_DIR", str(tmp_path))


def test_default_text100_matches_fixed_protocol(tmp_path):
    """Run all hundred unchanged text prompts through real generation and scoring boundaries."""
    task = trivia()
    selection = json.loads((DATA_DIR / "text100-selection.json").read_text())
    assert [s.id for s in task.dataset] == selection["selected_ids"]
    assert len(task.dataset) == 100
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
    assert log.status == "success" and len(log.samples) == 100
    for sample in read_eval_log(log.location).samples:
        assert sample.error is None
        assert sample.scores["strict_letter"].value == {"accuracy": "C", "format": "C"}
        assert [m.role for m in sample.messages] == ["system", "user", "assistant"]
        assert not any(isinstance(c, ContentImage) for c in sample.messages[1].content)


def test_archived_image_question_remains_explicit(tmp_path):
    """Keep the original image protocol available only through explicit archive settings."""
    task = trivia(question_set="all200", include_images=True, sample_ids=["sts1-041"])
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
