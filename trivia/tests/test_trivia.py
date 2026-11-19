"""Exercise scoring, image transport, independence, filters, and epochs through Inspect."""

import json

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
        trivia(sample_ids=[question_id]),
        model=model,
        log_dir=str(tmp_path),
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
        trivia(sample_ids=["sts1-001"]),
        model=model,
        log_dir=str(tmp_path),
        display="none",
    )[0]
    assert log.samples[0].scores["strict_letter"].value == {
        "accuracy": "I",
        "format": "C",
    }


def test_full_dataset_and_smoke_independence(tmp_path):
    """Carry real artwork and independent prompts through two Inspect epochs."""
    full = trivia()
    assert len(full.dataset) == 200
    assert (
        len(trivia(game="sts2", category="cards", include_images=False).dataset) == 40
    )
    task = trivia(smoke=True)
    assert len(task.dataset) == 12
    assert {s.metadata["game"] for s in task.dataset} == {"sts1", "sts2"}
    assert len([s for s in task.dataset if s.metadata["kind"] == "art_to_title"]) == 2
    outputs = [ModelOutput.from_content("mockllm/model", "A")] * 24
    log = inspect_eval(
        task,
        model=get_model("mockllm/model", custom_outputs=outputs),
        epochs=2,
        log_dir=str(tmp_path),
        display="none",
    )[0]
    assert log.status == "success"
    assert len(log.samples) == 24
    assert all(s.error is None for s in log.samples)
    for sample in read_eval_log(log.location).samples:
        assert [m.role for m in sample.messages] == ["system", "user", "assistant"]
        assert not sample.messages[-1].tool_calls
        assert "single uppercase letter" in sample.messages[0].text
        if sample.metadata["kind"] == "art_to_title":
            images = [
                c for c in sample.messages[1].content if isinstance(c, ContentImage)
            ]
            assert len(images) == 1
            assert images[0].image.startswith(("attachment:", "data:image/png;base64,"))


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
