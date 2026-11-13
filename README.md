# Slay the Spire visual smoke

This standalone Inspect AI task tests a visual game runtime on Generality Hawk. The model plays Ironclad at Ascension 20, reads the first enemy's article from a user-provided offline wiki, defeats one encounter, and stops.

It adapts the [published SpireClimb methodology](https://epoch.ai/benchmarks/spireclimb). Epoch's implementation and prompt were not available during this work. This package is an independent smoke task, with no full-run benchmark score or claim of exact reproduction.

## Installation and use

Install the package with `pip install .`. A licensed Linux copy of the game, ModTheSpire, BaseMod, CommunicationMod, DeterminismFix, Unlock Everything, and preference files are supplied separately in a private runtime archive. The archive is not committed to this repository. Set `STS_ASSET_URL` to a temporary private download URL for that archive.

Run `inspect eval sts_hawk/first_combat --model openrouter/openai/gpt-6-luna` on the intended Linux infrastructure. `sts_hawk/runtime_probe` exercises the same setup, screenshot and scoring paths without generating a model response. Real model evaluation is intended to run on Hawk; local tests use mockllm.

The sandbox installs Java 8, TigerVNC, graphics/audio dependencies and the stock Inspect computer backend into Ubuntu 24.04. It renders at 1280×720. Fast Mode and SuperFastMode are disabled; Unlock Everything is enabled. CommunicationMod is used only by controller setup and deterministic scoring. The model receives no text-state or game-command tool.

## Configuration

`src/sts_hawk/run_configs/default.yaml` owns task, solver, generation and limit defaults. Native Inspect run-config and solver overrides remain available. Setup remains outside the replaceable solver. Sandbox resources live in `assets/compose.yaml`; two CPUs and 4 GB are initial single-sample smoke allocations, not measured production batch requirements.

The configuration selects one seeded Ironclad A20 sample, stock Inspect ReAct and `computer()`, and an offline `wiki` tool. It retains one screenshot in model context. GPT-6 Luna's verified 1,050,000-token context gives a 787,500-token compaction trigger under the user's 75% policy; maximum response output is 128,000 tokens. Reasoning effort is `max`, matching Epoch's published choice. Model and billing-route selection belongs to the Hawk launch configuration.

This is a new smoke task with no historical implementation of its own, so it has no `original.yaml`. Differences from Epoch's full evaluation are deliberate: first-combat scope, new prompt and seed, offline Fandom wiki instead of the published web lookup, and the user's 75% compaction policy instead of Epoch's published 300k threshold. It does not reproduce the complete A20 Heart evaluation across characters and seeds.

## Result and logs

The smoke pass requires both a first-floor combat reward screen while alive and a relevant enemy article returned by the wiki tool before victory. The observer checks after each ReAct iteration and stops before the next model generation on victory or death. An early submission or missing wiki read fails the smoke; infrastructure and malformed-state errors raise instead of becoming a loss. The grader does not trust the model's final claim.

Wiki reads and trusted observations persist in Inspect's typed store and `.eval` log. Wiki text retains original Fandom URLs. The copied computer backend is from Inspect AI 0.3.289 and retains its MIT license.

For live viewing, set `STS_VIEWER_PORT` in the Hawk runner environment and enable Hawk `log_realtime`. The optional hook serves Inspect View only on the runner's loopback interface. An authenticated `hawk attach RUN --port PORT --local-port PORT` relay makes it reachable at localhost on the viewing Mac. The viewer terminates with the evaluation; final `.eval` archives can be downloaded and viewed locally afterwards.

## Validation

`pytest tests` covers wiki articles, observer error attribution, death and victory, and a mockllm end-to-end trajectory through stock computer-tool parsing, wiki lookup, typed history, automatic termination, and the real scorer. These tests simulate external game transport; a separate native Linux runtime probe verifies the actual game and screenshot path before the Luna smoke. `ruff check .` and `ruff format --check .` cover authored code. Inspect's vendored computer backend is excluded from formatting changes.
