import base64
import tempfile
from pathlib import Path
from typing import Any

import yaml
from inspect_ai import Task, task
from inspect_ai.dataset import Sample
from inspect_ai.model import ContentImage, ContentText, GenerateConfig
from inspect_ai.scorer import includes
from inspect_ai.solver import Generate, Solver, TaskState, solver
from inspect_ai.solver import generate as generate_response
from inspect_ai.tool import computer

from sts_hawk import agent, scorers
from sts_hawk.prompts import PROMPTS
from sts_hawk.run_config import default_run_config
from sts_hawk.runtime import prepare_game

DEFAULTS = default_run_config()
ARGS = DEFAULTS["task"]["args"]


def sandbox_config(image: str) -> str:
    """Write the sample's Kubernetes-compatible single-service Compose config."""
    compose = yaml.safe_load(
        (Path(__file__).parent / "assets/compose.yaml").read_text()
    )
    compose["services"]["default"]["image"] = image
    path = Path(tempfile.mkdtemp(prefix="sts-sandbox-")) / "compose.yaml"
    path.write_text(yaml.safe_dump(compose))
    return str(path)


@task
def first_combat(
    character: str = ARGS["character"],
    ascension: int = ARGS["ascension"],
    seed: str = ARGS["seed"],
    prompt_name: str = ARGS["prompt_name"],
    scorer_name: str = ARGS["scorer_name"],
    setup_timeout: int = ARGS["setup_timeout"],
    observer_timeout: int = ARGS["observer_timeout"],
    sandbox_image: str = ARGS["sandbox_image"],
) -> Task:
    """Compose one visual A20 first-combat sample using the local wiki."""
    selected = PROMPTS[prompt_name]
    slv = getattr(agent, DEFAULTS["solver"]["solver"].split("/")[-1])
    scorer_factory = getattr(scorers, scorer_name)
    return Task(
        name="sts_first_combat",
        dataset=[
            Sample(
                id=f"{character.lower()}-a{ascension}-{seed}",
                input=selected.text.format(character=character, ascension=ascension),
            )
        ],
        setup=prepare_game(character, ascension, seed, setup_timeout, observer_timeout),
        solver=slv(**DEFAULTS["solver"]["args"]),
        scorer=scorer_factory(observer_timeout=observer_timeout),
        sandbox=("docker", sandbox_config(sandbox_image)),
        config=GenerateConfig(**DEFAULTS["generate_config"]),
        **DEFAULTS["eval_config"],
        metadata={
            "purpose": "One-combat infrastructure smoke, not a SpireClimb score",
            "prompt_origin": selected.origin_note,
            "wiki": "User-provided offline Fandom scrape (750 pages)",
            "model_visible": "Stock Inspect computer screenshots/actions, local wiki, submit",
            "oracle": "Host-only CommunicationMod setup and scoring; no oracle tools exposed to model",
            "differences_from_epoch": "Offline wiki; first combat only; new prompt and seed; 75% context compaction",
        },
    )


@solver
def capture_runtime() -> Solver:
    """Capture the real sandbox once without calling a paid model."""

    async def solve(state: TaskState, generate: Generate) -> TaskState:
        """Exercise the installed stock computer tool before the real model smoke."""
        from inspect_ai.model import ChatMessageUser

        state.messages.append(
            ChatMessageUser(content=await computer()(action="screenshot"))
        )
        return state

    return solve


@task
def runtime_probe(**kwargs: Any) -> Task:
    """Reuse the full setup and scoring path for a no-inference runtime preflight."""
    result = first_combat(**kwargs)
    result.solver = capture_runtime()
    return result


@task
def provider_probe() -> Task:
    """Verify a single paid vision request on the selected Hawk provider route."""
    png = (Path(__file__).parent / "assets/provider-probe.png").read_bytes()
    return Task(
        name="sts_provider_probe",
        dataset=[
            Sample(
                id="vision-tile",
                input=[
                    ContentText(text="Name this tile's color using one word."),
                    ContentImage(
                        image="data:image/png;base64," + base64.b64encode(png).decode()
                    ),
                ],
                target="white",
            )
        ],
        solver=generate_response(),
        scorer=includes(),
        config=GenerateConfig(**DEFAULTS["generate_config"]),
        epochs=1,
    )
