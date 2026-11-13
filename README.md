# Slay the Spire visual smoke

This standalone Inspect AI task runs a first-combat visual smoke on Generality Hawk. GPT-6 Luna plays Ironclad at Ascension 20, reads the first enemy's article from an offline wiki, defeats one encounter, and submits the highest floor reached as an integer.

It is an independent adaptation of [Epoch's published SpireClimb methodology](https://epoch.ai/benchmarks/spireclimb). Epoch's complete implementation and prompt were unavailable. This task has no automated grader and does not produce a SpireClimb benchmark score.

## Usage

Install the package with `pip install .`. Supply a licensed Linux game and the mods separately in a private runtime archive; game files are excluded from this repository. Set `STS_ASSET_URL` to a temporary private download URL for that archive.

On the intended Linux infrastructure:

```bash
inspect eval sts_hawk/first_combat --model openrouter/openai/gpt-6-luna \
  -M responses_api=true -M responses_store=false
```

Real model evaluations run on Hawk. Local validation uses mockllm. `sts_hawk/runtime_probe` performs the same installation and captures a screenshot without a model generation. These are separate checks: provider connectivity does not prove the game runs, and a runtime screenshot does not prove the agent can play.

### Configuration

`src/sts_hawk/run_configs/default.yaml` owns task, solver, generation and evaluation defaults. Copy it to change settings; native Inspect run-config and solver overrides remain available. Setup stays outside the replaceable solver. This is a new smoke task with no upstream implementation to reproduce, so there is no `original.yaml`.

The default selects one Ironclad A20 sample, stock Inspect ReAct and `computer()`, and the offline `wiki` tool. It retains one screenshot in context. Compaction is triggered at 787,500 tokens, following the user's 75% policy for Luna's verified 1,050,000-token context. Maximum response output is 128,000 tokens and reasoning effort is `max`. Model and billing-route selection belong to the Hawk launch configuration.

The computer tool is exposed as `desktop` using Inspect's `tool_with`; its actions and backend are unchanged. This keeps it as a function tool because Inspect's native OpenAI computer mode forces `store=true`, which OpenRouter's stateless Responses API rejects. Luna requires Responses for function calling with reasoning. Pass `responses_api: true` and `responses_store: false` in the Hawk model arguments too. The task supports Hawk’s pinned Inspect 0.3.286.dev10+g3a44082ca and newer releases. On that older Hawk build, include `agent-client-protocol==0.12.1` in runner packages: ACP 1.0 removed an import it needs. Inspect 0.3.289 fixes that upstream, but Hawk currently pins its framework version.

Differences from Epoch's full benchmark include first-combat scope, a new prompt, an offline Fandom wiki, the 75% compaction policy and no automated grading. No seed list or A20 Heart completion benchmark is implemented.

## Runtime

The sandbox installs Java 8, TigerVNC, graphics dependencies and Inspect's stock computer backend into Ubuntu 24.04, rendering at 1280×720. BaseMod, DeterminismFix and Unlock Everything are enabled. Fast Mode and SuperFastMode are disabled. The task uses graphical input; it does not load CommunicationMod or expose a game-state command tool.

Sandbox resources live in `assets/compose.yaml`. Two CPUs and 4 GB are initial single-smoke allocations, not measured production batch requirements. Container internet access is enabled for OS installation and the private archive download. Runtime assets and download URLs must stay private.

## Parameters

`first_combat` accepts `character` (`IRONCLAD`), `ascension` (`20`), `prompt_name` (`first_combat`), `setup_timeout` (`900` seconds), `command_timeout` (`180` seconds) and `sandbox_image` (`ubuntu:24.04`). The requested character and difficulty are instructions for the model to select and verify visually; no hidden controller starts a run for it.

The `visual_agent` solver accepts `max_screenshots` (`1`), `tool_timeout` (`180` seconds) and `compaction_threshold` (`787500` tokens). The offline wiki contains 750 pages and returns original article text and source URLs. See `THIRD_PARTY.md` for attribution. The vendored stock computer backend retains Inspect's MIT license.

## Submission and logs

The agent finishes with `submit(max_floor: int)`. Inspect stores the integer as the final completion and retains the tool call. This is an unverified self-report. The user checks screenshots to determine whether the first encounter was won and whether the floor report is accurate. Wiki reads are recorded in the typed Inspect store. There is no grader or aggregate score.

Hawk's live viewer shows actions and screenshots when `log_realtime` is enabled. No local viewer or relay is required. Installation and sandbox failures remain errors rather than game losses.

## Validation

Run `pytest tests`, `ruff check .` and `ruff format --check .`. Tests exercise the actual task setup, stock computer parser, wiki tool, invalid and valid integer submissions, unscored completion, and setup-error propagation through mockllm. They also exercise the real Hawk Compose-to-Kubernetes conversion. External execution is simulated in local tests; the separate Linux runtime probe must establish actual game startup before the paid gameplay smoke.

Validate the real Docker runtime and tools locally with mockllm before launching on Hawk. Keep local containers bounded at two CPUs and 4 GB, reuse cached OS layers, mount the private archive read-only for installation, and remove the test containers afterwards. A scripted menu click and wiki read verify integration, not model playing ability.
