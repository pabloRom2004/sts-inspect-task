import json
import os

from inspect_ai import eval as inspect_eval
from inspect_ai.model import ModelOutput, get_model
from spire_trivia import trivia
from spire_trivia.dataset import DATA_DIR
from spire_trivia.scorers import final_choice


def test_patch_and_carryover():
    previous = {s.id: s for s in trivia(question_set="text200-v6").dataset}
    current = trivia().dataset
    protocol = json.loads((DATA_DIR / "text200-v7-protocol.json").read_text())
    changed = []
    for sample in current:
        old = previous[sample.id]
        if sample.metadata["game"] == "sts1":
            assert [m.text for m in sample.input] == [
                m.text for m in old.input
            ] and sample.target == old.target
        else:
            assert sample.input[1].text.startswith(
                "Answer for Slay the Spire 2 v0.107.1 (Major Update #2, released 19 June 2026 UTC).\n\n"
            )
            if (
                sample.input[1].text.partition("\n\n")[2]
                != old.input[1].text.partition("\n\n")[2]
                or sample.target != old.target
            ):
                changed.append(sample.id)
    assert len(current) == 200 and changed == protocol["reask_ids"]


def test_final_line_scoring(tmp_path):
    assert all(
        not final_choice(s) for s in ["", "A or B", "B.", "i", "I\nactually perhaps A"]
    )
    task = trivia(sample_ids=["sts2-301", "sts2-302", "sts2-303"])
    responses = [
        "My conclusion follows.\n" + task.dataset[0].target,
        "Unsure.\nI",
        "A or B",
    ]
    model = get_model(
        "mockllm/model",
        custom_outputs=[
            ModelOutput.from_content("mockllm/model", s) for s in responses
        ],
    )
    log = inspect_eval(
        task,
        model=model,
        max_samples=1,
        display="none",
        log_dir=os.environ.get("SPIRE_TRIVIA_TEST_LOG_DIR", str(tmp_path)),
    )[0]
    assert log.status == "success"
    scores = [s.scores["abstention_letter"] for s in log.samples]
    assert [s.metadata["outcome"] for s in scores] == [
        "correct",
        "abstained",
        "invalid",
    ]
    assert all(s.value["format"] == "I" for s in scores)
