"""Verify abstention, negative scoring, and unchanged factual inputs through Inspect."""

import os

import pytest
from inspect_ai import eval as inspect_eval
from inspect_ai.log import read_eval_log
from inspect_ai.model import ModelOutput, get_model
from spire_trivia import trivia


def abstention_task(**kwargs):
    """Select the complete nine-choice protocol with explicit historical-safe selectors."""
    return trivia(
        question_set="text200-v3",
        system_prompt="knowledge_abstention",
        scorer="abstention_letter",
        **kwargs,
    )


@pytest.mark.parametrize(
    "response,outcome,points,valid",
    [
        ("E", "correct", 1, True),
        ("A", "wrong", -1, True),
        ("I", "abstained", 0, True),
        (" I \n", "abstained", 0, True),
        ("I don't know", "invalid", -1, False),
        ("i", "invalid", -1, False),
        ("I.", "invalid", -1, False),
        ("J", "invalid", -1, False),
        ("", "invalid", -1, False),
        ("A I", "invalid", -1, False),
    ],
)
def test_abstention_score_round_trip(tmp_path, response, outcome, points, valid):
    """Exercise real generation, scoring, and log serialization for each response class."""
    model = get_model(
        "mockllm/model",
        custom_outputs=[ModelOutput.from_content("mockllm/model", response)],
    )
    log = inspect_eval(
        abstention_task(sample_ids=["sts1-111"]),
        model=model,
        log_dir=os.environ.get("SPIRE_TRIVIA_TEST_LOG_DIR", str(tmp_path)),
        display="none",
    )[0]
    assert log.status == "success"
    sample = read_eval_log(log.location).samples[0]
    score = sample.scores["abstention_letter"]
    assert sample.error is None and score.value["net_score"] == points
    assert score.metadata["outcome"] == outcome
    assert score.value["format"] == ("C" if valid else "I")
    assert [m.role for m in sample.messages] == ["system", "user", "assistant"]
    assert "incorrect answer scores -1" in sample.messages[0].text
    assert sample.messages[1].text.endswith("I. I don't know")


def test_abstention_filters_and_factual_equivalence():
    """Keep both games at 100 questions and preserve every factual choice and target."""
    old = {
        s.id: s
        for s in trivia(
            question_set="text200-v2",
            system_prompt="knowledge_only",
            scorer="strict_letter",
        ).dataset
    }
    for game in ["sts1", "sts2"]:
        new = abstention_task(game=game)
        assert len(new.dataset) == 100
        for s in new.dataset:
            assert s.target == old[s.id].target
            assert s.input[1].text == old[s.id].input[1].text + "\nI. I don't know"
            assert s.metadata == old[s.id].metadata


def test_abstention_cannot_use_baseline_scoring():
    """Reject mismatched scoring and question protocols before any inference."""
    with pytest.raises(ValueError):
        trivia(question_set="text200-v3")
    with pytest.raises(ValueError):
        trivia(scorer="strict_letter")


def test_negative_and_zero_scores_survive_epoch_reduction(tmp_path):
    """Verify numeric means preserve penalties and abstentions across repeated attempts."""
    model = get_model(
        "mockllm/model",
        custom_outputs=[
            ModelOutput.from_content("mockllm/model", x) for x in ["A", "I"]
        ],
    )
    log = inspect_eval(
        abstention_task(sample_ids=["sts1-111"]),
        model=model,
        epochs=2,
        max_samples=1,
        log_dir=os.environ.get("SPIRE_TRIVIA_TEST_LOG_DIR", str(tmp_path)),
        display="none",
    )[0]
    result = read_eval_log(log.location)
    assert [
        s.scores["abstention_letter"].value["net_score"] for s in result.samples
    ] == [-1, 0]
    metric = result.results.scores[0].metrics["mean"].value
    assert metric == -0.5
