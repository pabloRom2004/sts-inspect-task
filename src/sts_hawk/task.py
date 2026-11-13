import tempfile
from pathlib import Path
from typing import Any

import yaml
from inspect_ai import Task, task
from inspect_ai.dataset import Sample
from inspect_ai.model import ChatMessageUser, GenerateConfig
from inspect_ai.solver import Generate, Solver, TaskState, solver
from inspect_ai.tool import computer

from sts_hawk import agent
from sts_hawk.prompts import PROMPTS
from sts_hawk.run_config import default_run_config
from sts_hawk.runtime import checked_exec, logger, prepare_game

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
    prompt_name: str = ARGS["prompt_name"],
    setup_timeout: int = ARGS["setup_timeout"],
    command_timeout: int = ARGS["command_timeout"],
    sandbox_image: str = ARGS["sandbox_image"],
) -> Task:
    """Compose a minimal Slay the Spire agent task with an offline wiki."""
    selected = PROMPTS[prompt_name]
    slv = getattr(agent, DEFAULTS["solver"]["solver"].split("/")[-1])
    return Task(
        name=f"sts_{prompt_name}",
        dataset=[
            Sample(
                id=f"{character.lower()}-a{ascension}-{prompt_name.replace('_', '-')}",
                input=selected.text.format(
                    character=character.title(), ascension=ascension
                ),
            )
        ],
        setup=prepare_game(setup_timeout, command_timeout),
        solver=slv(**DEFAULTS["solver"]["args"]),
        sandbox=("docker", sandbox_config(sandbox_image)),
        config=GenerateConfig(**DEFAULTS["generate_config"]),
        **DEFAULTS["eval_config"],
        metadata={
            "purpose": "Minimal gameplay task, not a SpireClimb score",
            "prompt_origin": selected.origin_note,
            "wiki": "User-provided offline Fandom scrape (750 pages)",
            "model_visible": "Stock desktop, bash and python tools; wiki at /opt/sts/wiki.md; submit",
            "grading": "Unscored; verify gameplay and self-reported floor manually",
            "differences_from_epoch": "Offline wiki file; general shell/Python access; user-requested minimal prompt; 75% context compaction; no grader",
        },
    )


@solver
def capture_runtime() -> Solver:
    """Capture the real sandbox once without calling a paid model."""

    async def solve(state: TaskState, generate: Generate) -> TaskState:
        """Exercise the installed stock computer tool before the real model smoke."""
        try:
            state.messages.append(
                ChatMessageUser(
                    content=await computer(timeout=180)(action="wait", duration=15)
                )
            )
        finally:
            logger.info(
                "Runtime diagnostics:\n%s",
                await checked_exec(
                    [
                        "bash",
                        "-lc",
                        (
                            "printf 'PID 1: '; tr '\\0' ' ' < /proc/1/cmdline; "
                            "printf '\\n'; tail -30 /tmp/sts-startup.log /tmp/game.log "
                            "/tmp/xvnc.log 2>/dev/null || true"
                        ),
                    ],
                    180,
                ),
            )
        return state

    return solve


@task
def runtime_probe(**kwargs: Any) -> Task:
    """Reuse the setup for a no-inference screenshot preflight."""
    result = first_combat(**kwargs)
    result.solver = capture_runtime()
    return result
