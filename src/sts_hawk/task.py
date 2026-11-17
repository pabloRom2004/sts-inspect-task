import tempfile
from pathlib import Path
from typing import Any

import yaml
from inspect_ai import Task, task
from inspect_ai.dataset import Sample
from inspect_ai.log import transcript
from inspect_ai.model import ChatMessageUser, GenerateConfig
from inspect_ai.solver import Generate, Solver, TaskState, solver
from inspect_ai.tool import computer

from sts_hawk import agent
from sts_hawk.prompts import PROMPTS
from sts_hawk.run_config import default_run_config
from sts_hawk.runtime import checked_exec, logger, prepare_game

DEFAULTS = default_run_config()
ARGS = DEFAULTS["task"]["args"]


def sandbox_config(image: str, cpu: str, memory: str, height: int | None = None) -> str:
    """Write the sample's Kubernetes-compatible single-service Compose config."""
    compose = yaml.safe_load(
        (Path(__file__).parent / "assets/compose.yaml").read_text()
    )
    compose["services"]["default"]["image"] = image
    compose["services"]["default"]["deploy"]["resources"]["limits"].update(
        cpus=cpu, memory=memory
    )
    if height is not None:
        compose["services"]["default"]["environment"]["HEIGHT"] = str(height)
    path = Path(tempfile.mkdtemp(prefix="sts-sandbox-")) / "compose.yaml"
    path.write_text(yaml.safe_dump(compose))
    return str(path)


@task
def first_combat(
    character: str = ARGS["character"],
    ascension: int = ARGS["ascension"],
    game_seed: str | int | None = ARGS["game_seed"],
    prompt_name: str = ARGS["prompt_name"],
    setup_timeout: int = ARGS["setup_timeout"],
    command_timeout: int = ARGS["command_timeout"],
    sandbox_image: str = ARGS["sandbox_image"],
    sandbox_cpu: str = ARGS["sandbox_cpu"],
    sandbox_memory: str = ARGS["sandbox_memory"],
    processor_count: int = ARGS["processor_count"],
    renderer_threads: int = ARGS["renderer_threads"],
    java_heap_mb: int = ARGS["java_heap_mb"],
) -> Task:
    """Compose a minimal Slay the Spire agent task with an offline wiki."""
    selected = PROMPTS[prompt_name]
    slv = getattr(agent, DEFAULTS["solver"]["solver"].split("/")[-1])
    return Task(
        name=f"sts_{prompt_name}",
        dataset=[
            Sample(
                id=(
                    f"{character.lower()}-a{ascension}-{prompt_name.replace('_', '-')}"
                    + (f"-seed-{game_seed}" if game_seed is not None else "")
                ),
                input=selected.render(
                    character=character.title(),
                    ascension=ascension,
                    game_seed=game_seed,
                ),
                metadata={"requested_game_seed": game_seed},
            )
        ],
        setup=prepare_game(
            setup_timeout,
            command_timeout,
            processor_count=processor_count,
            renderer_threads=renderer_threads,
            java_heap_mb=java_heap_mb,
        ),
        solver=slv(**DEFAULTS["solver"]["args"]),
        sandbox=("docker", sandbox_config(sandbox_image, sandbox_cpu, sandbox_memory)),
        config=GenerateConfig(**DEFAULTS["generate_config"]),
        **DEFAULTS["eval_config"],
        metadata={
            "purpose": "Minimal gameplay task, not a SpireClimb score",
            "sandbox_cpu": sandbox_cpu,
            "sandbox_memory": sandbox_memory,
            "processor_count": processor_count,
            "renderer_threads": renderer_threads,
            "java_heap_mb": java_heap_mb,
            "prompt_origin": selected.origin_note,
            "requested_game_seed": game_seed,
            "wiki": "User-provided offline Fandom scrape (750 pages)",
            "model_visible": "Desktop, sandbox shell/Python and integer submit; wiki at /opt/sts/wiki.md; harness recorded in solver configuration",
            "grading": "Unscored; verify gameplay and self-reported floor manually",
            "differences_from_epoch": "Offline wiki file; general shell/Python access; user-requested minimal prompt; 75% context compaction; no grader",
        },
    )


@task
def second_game(
    character: str = ARGS["character"],
    ascension: int = DEFAULTS["sts2"]["ascension"],
    game_seed: str | int | None = ARGS["game_seed"],
    prompt_name: str = DEFAULTS["sts2"]["prompt_name"],
    setup_timeout: int = ARGS["setup_timeout"],
    command_timeout: int = ARGS["command_timeout"],
    sandbox_image: str = ARGS["sandbox_image"],
    frame_rate_limit: int = DEFAULTS["sts2"]["frame_rate_limit"],
    log_frame_rate: bool = DEFAULTS["sts2"]["log_frame_rate"],
    sandbox_cpu: str = ARGS["sandbox_cpu"],
    sandbox_memory: str = ARGS["sandbox_memory"],
    processor_count: int = ARGS["processor_count"],
    renderer_threads: int = ARGS["renderer_threads"],
) -> Task:
    """Reuse the agent and integer submission for StS2's three-Act A10 game."""
    if not 0 <= ascension <= 10:
        raise ValueError("Slay the Spire 2 v0.107.1 supports Ascension 0 through 10.")
    if frame_rate_limit < 0:
        raise ValueError("The frame rate limit must be nonnegative.")
    result = first_combat(
        character=character,
        ascension=ascension,
        game_seed=game_seed,
        prompt_name=prompt_name,
        setup_timeout=setup_timeout,
        command_timeout=command_timeout,
        sandbox_image=sandbox_image,
        sandbox_cpu=sandbox_cpu,
        sandbox_memory=sandbox_memory,
        processor_count=processor_count,
        renderer_threads=renderer_threads,
    )
    sample = result.dataset[0]
    sample.id = f"sts2-{sample.id}"
    sample.metadata["game"] = "sts2"
    slv = getattr(agent, DEFAULTS["solver"]["solver"].split("/")[-1])
    result.metadata.update(
        game="sts2",
        game_version="v0.107.1",
        frame_rate_limit=frame_rate_limit,
        log_frame_rate=log_frame_rate,
        wiki="No offline StS2 wiki supplied",
        model_visible="Desktop, sandbox shell/Python and integer submit",
        differences_from_epoch="Built-in --force-steam=off startup; no offline StS2 wiki; general shell/Python; user prompt; 75% compaction; no grader",
    )
    result.metadata.pop("java_heap_mb", None)
    return Task(
        name=f"sts2_{prompt_name.removesuffix('_sts2')}",
        dataset=result.dataset,
        setup=prepare_game(
            setup_timeout,
            command_timeout,
            game="sts2",
            frame_rate_limit=frame_rate_limit,
            log_frame_rate=log_frame_rate,
            processor_count=processor_count,
            renderer_threads=renderer_threads,
        ),
        solver=slv(**{**DEFAULTS["solver"]["args"], "wiki_path": None}),
        sandbox=(
            "docker",
            sandbox_config(
                sandbox_image,
                sandbox_cpu,
                sandbox_memory,
                height=DEFAULTS["sts2"]["desktop_height"],
            ),
        ),
        config=result.config,
        metadata=result.metadata,
        **DEFAULTS["eval_config"],
    )


@solver
def capture_runtime(
    wait_seconds: int = DEFAULTS["runtime_probe"]["wait_seconds"],
    actions: list[dict[str, Any]] | None = None,
    capture_profile: bool = False,
) -> Solver:
    """Capture the real sandbox once without calling a paid model."""

    async def solve(state: TaskState, generate: Generate) -> TaskState:
        """Exercise the installed stock computer tool before the real model smoke."""
        try:
            if state.metadata.get("game") == "sts2":
                await checked_exec(
                    [
                        "bash",
                        "-lc",
                        (
                            "until grep -Fq 'main menu loaded (complete)' "
                            "/tmp/game.log 2>/dev/null; do "
                            "if [ -f /tmp/sts-failed ]; then "
                            "tail -n 40 /tmp/game.log; exit 1; fi; sleep 1; done"
                        ),
                    ],
                    180,
                )
            state.messages.append(
                ChatMessageUser(
                    content=await computer(timeout=180)(
                        action="wait", duration=wait_seconds
                    )
                )
            )
            for action in actions or []:
                state.messages.append(
                    ChatMessageUser(content=await computer(timeout=180)(**action))
                )
            if capture_profile:
                profile = await checked_exec(
                    [
                        "bash",
                        "-lc",
                        (
                            "set -o pipefail; "
                            "tar -C /root/.local/share/SlayTheSpire2 -czf - default "
                            "| base64 -w 0"
                        ),
                    ],
                    180,
                )
                transcript().info(
                    {"profile_archive_base64": profile},
                    source="sts_hawk.runtime_probe",
                )
        finally:
            diagnostics = await checked_exec(
                [
                    "bash",
                    "-lc",
                    (
                        "printf 'PID 1: '; tr '\\0' ' ' < /proc/1/cmdline; "
                        "printf '\\n=== Renderer startup ===\\n'; "
                        "head -n 15 /tmp/game.log 2>/dev/null; "
                        "printf '\\n'; "
                        "for file in /tmp/sts-startup.log /tmp/game.log "
                        "/tmp/xvnc.log "
                        "/root/.local/share/SlayTheSpire2/logs/godot.log; do "
                        'if [ -f "$file" ]; then '
                        "printf '\\n=== %s ===\\n' \"$file\"; "
                        'tail -n 200 "$file"; fi; done; '
                        "printf '\\n=== Container resource counters ===\\n'; "
                        "for file in /sys/fs/cgroup/memory.current "
                        "/sys/fs/cgroup/memory.peak /sys/fs/cgroup/memory.max "
                        "/sys/fs/cgroup/memory.events /sys/fs/cgroup/cpu.stat "
                        "/sys/fs/cgroup/cpu.max; do "
                        'if [ -r "$file" ]; then printf "%s: " "$file"; '
                        'cat "$file"; fi; done; '
                        "printf '\\n=== Process memory and state ===\\n'; "
                        "for file in /proc/[0-9]*/status; do "
                        'if [ -r "$file" ]; then printf "%s\\n" "$file"; '
                        "awk '/^(Name|State|VmRSS|VmPeak|Threads):/' "
                        '"$file" 2>/dev/null || true; fi; done'
                    ),
                ],
                180,
            )
            transcript().info(
                {"runtime_diagnostics": diagnostics}, source="sts_hawk.runtime_probe"
            )
            logger.info("Runtime diagnostics:\n%s", diagnostics)
        return state

    return solve


@task
def runtime_probe(
    game: str = "sts1",
    wait_seconds: int = DEFAULTS["runtime_probe"]["wait_seconds"],
    actions: list[dict[str, Any]] | None = None,
    capture_profile: bool = False,
    **kwargs: Any,
) -> Task:
    """Reuse the setup for a no-inference screenshot preflight."""
    if game not in {"sts1", "sts2"}:
        raise ValueError(f"Unknown game: {game}")
    result = second_game(**kwargs) if game == "sts2" else first_combat(**kwargs)
    result.solver = capture_runtime(
        wait_seconds=wait_seconds, actions=actions, capture_profile=capture_profile
    )
    return result
