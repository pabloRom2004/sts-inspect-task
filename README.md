# Slay the Spire agent

This standalone Inspect AI task runs Slay the Spire on Generality Hawk with Inspect ReAct or native Codex CLI. ReAct is the default. The task prompt is exactly:

> play Slay the Spire for me as Ironclad
>
> Defeat the Heart to win.
>
> Play one round and do not restart the game. Play until victory or defeat.
>
> Enter seed 1 in the game's seed field before starting the run.
>
> An offline Slay the Spire wiki is available at /opt/sts/wiki.md.

The agent has desktop, shell and Python tools and can create files and run code in its sandbox. The offline wiki location is included in the task prompt and ReAct's Bash tool description. There is no custom wiki tool or required lookup sequence.

It is an independent adaptation of [Epoch's published SpireClimb methodology](https://epoch.ai/benchmarks/spireclimb). Epoch's complete implementation and prompt were unavailable. This task has no automated grader and does not produce a SpireClimb benchmark score.

## Usage

Install the package with `pip install .`. Supply a licensed Linux game and the mods separately in a private runtime archive; game files are excluded from this repository. Set `STS_ASSET_URL` to a temporary private download URL for that archive.

On the intended Linux infrastructure:

```bash
inspect eval sts_hawk/first_combat --model openrouter/openai/gpt-6-luna \
  -M responses_api=true -M responses_store=false
```

For the full-game A20 attempt, pass `-T prompt_name=beat_game`. Its prompt is:

> Try to beat Slay the Spire on Ascension 20 as Ironclad.
>
> Defeat the Heart to win.
>
> Play one round and do not restart the game. Play until victory or defeat.
>
> Enter seed 1 in the game's seed field before starting the run.
>
> An offline Slay the Spire wiki is available at /opt/sts/wiki.md.

The general tools and integer submission are unchanged. No first-combat stopping rule applies.

For a bounded StS1 integration check, select `-T prompt_name=first_combat_smoke`. This separate prompt asks the model to read the wiki about its first enemy, finish that combat and call `submit` with the maximum floor reached. It retains the character, ascension, seed and no-restart instructions. It does not require a full-game victory and is not a performance benchmark prompt. The two existing StS1 prompts and their defaults are unchanged.

Real model evaluations run on Hawk. Local validation uses mockllm. `sts_hawk/runtime_probe` performs the same installation and captures a screenshot without a model generation. These are separate checks: provider connectivity does not prove the game runs, and a runtime screenshot does not prove the agent can play.

### Configuration

`src/sts_hawk/run_configs/default.yaml` owns task, solver, generation and evaluation defaults. Copy it to change settings; native Inspect run-config and solver overrides remain available. Setup stays outside the replaceable solver. This is a new smoke task with no upstream implementation to reproduce, so there is no `original.yaml`.

The default selects one sample and stock Inspect ReAct with `computer()` exposed as `desktop`, `bash()` and `python()`. Up to the three latest desktop screenshots are sent to the model; the full screenshot history remains in the log. Hawk's pinned Inspect build has a per-tool count bug that otherwise drops the newest screenshot after Bash/Python calls. A version-scoped backport applies the upstream 0.3.289 fix. Keeping all screenshots was tested but hit the provider's 50-image request limit, so it is not the default. The same screenshot policy is applied before both native and summary compaction, because Inspect does not apply tool input handlers on those paths. Compaction is triggered at 787,500 tokens, following the user's 75% policy for Luna's verified 1,050,000-token context. Maximum response output is 128,000 tokens and reasoning effort is `max`. Model and billing-route selection belong to the Hawk launch configuration.

The computer tool is exposed as `desktop` using Inspect's `tool_with`, with input validation before stock action execution and the backend error-handling fixes described below. Its model-visible schema and screenshot filtering are preserved. This keeps it as a function tool because Inspect's native OpenAI computer mode forces `store=true`, which OpenRouter's stateless Responses API rejects. Luna requires Responses for function calling with reasoning. Pass `responses_api: true` and `responses_store: false` in the Hawk model arguments too. ReAct supports the older Hawk Inspect 0.3.286.dev10+g3a44082ca build and newer releases. On that older build, include `agent-client-protocol==0.12.1` in runner packages: ACP 1.0 removed an import it needs. Inspect 0.3.289 fixes that upstream; Codex requires at least that release.

### Codex CLI

Install the optional adapter with `pip install '.[codex]'`. It requires Inspect >=0.3.289 and pins [Inspect SWE](https://meridianlabs-ai.github.io/inspect_swe/codex_cli.html) 0.3.0. Select Codex through the existing solver parameter:

```bash
inspect eval sts_hawk/first_combat --model openrouter/openai/gpt-6-luna \
  -M responses_api=true -M responses_store=false \
  -S harness=codex -T prompt_name=beat_game
```

[Codex CLI 0.169.0](https://github.com/openai/codex/releases/tag/rust-v0.169.0) runs inside the same Linux game sandbox. Its own agent loop, instructions, code-mode tools, shell and file handling replace ReAct. Inspect SWE proxies inference back to the selected Inspect model and records it in `.eval`; the Codex process receives a placeholder proxy key, not the provider credential. The desktop and integer `submit` tools are exposed through MCP. Subagents, goal tools and native web search are disabled. Native shell and Python remain available, including access to `/opt/sts/wiki.md`.

`solver.args.codex` in `default.yaml` owns the native version, prompt/tool slug (`model_config`), context, compaction threshold and workspace paths. The slug is explicitly `gpt-6-luna` so an OpenRouter model name does not silently select Codex's generic fallback prompt. It selects Codex's local instructions and tools; it does not change the inference model. Change it deliberately when testing another model.

The Codex arm uses its native 272,000-token context. Codex reserves 5% and reports 258,400 usable tokens in its native token-count events, so its explicit automatic-compaction threshold is 193,800 (75% of that verified effective window). ReAct retains 1,050,000 and 787,500 respectively. Both arms keep the 128,000 per-response output limit and `max` reasoning through Inspect's effective generation config. These are context-management differences in the comparison, not identical harness settings.

The bridge removes all but the latest three images from outgoing model requests while retaining text and reasoning. Native Codex still owns its session history and compaction; this is not ReAct's compactor. Code-mode desktop calls must emit their returned image using `image(...)` for the next model request to include it. All executed desktop calls and their screenshots remain in tool events. On a valid submission, the next inference request receives a local integer final response and the run ends without a further provider call. If Codex exits normally without submitting, its final text is retained and `FloorSubmission:native_exit_without_submit` is set in the sample store. No floor is invented and the run is not labelled an infrastructure error. There is no automatic continuation after such a voluntary exit.

This is the supported open-source Codex CLI harness with the existing Inspect desktop backend. It does not recreate the Codex Desktop app's built-in computer-use implementation. Setup, sandbox and native-process failures remain evaluation errors. Native checkpoint/resume and full-game performance need separate remote validation; short scripted transport tests do not establish them.

Differences from Epoch's benchmark include the user-specified prompt, general shell/Python access, an offline Fandom wiki, the 75% compaction policy and no automated grading. The exact Epoch prompt has not been verified. Both prompts require defeating the Heart to win, but completion is not mechanically verified. The task requests one game seed at a time; it does not implement the full 15-seed benchmark.

## Runtime

The sandbox installs Java 8, TigerVNC, graphics dependencies and Inspect's stock computer backend into Ubuntu 24.04, rendering at 1280×720. BaseMod, DeterminismFix and Unlock Everything are enabled. Fast Mode and SuperFastMode are disabled. The task does not load CommunicationMod or expose a custom game-state command tool. Shell and Python access are ordinary sandbox tools, without a wiki-only restriction.

Startup explicitly focuses the game window. Without a window manager, Xvnc can leave keyboard focus on ModTheSpire's hidden launcher window even while mouse clicks reach the game.

Sandbox resources live in `assets/compose.yaml`. Two CPUs and 4 GB are initial single-smoke allocations, not measured production batch requirements. Container internet access is enabled for OS installation and the private archive download. Runtime assets and download URLs must stay private.

## Parameters

`first_combat` accepts `character` (`IRONCLAD`), `ascension` (`20`), `game_seed` (`"1"`), `prompt_name` (`first_combat`), `setup_timeout` (`900` seconds), `command_timeout` (`180` seconds) and `sandbox_image` (`ubuntu:24.04`). The `first_combat` entrypoint is retained for compatibility. The character parameter defaults to Ironclad. The `beat_game` and `first_combat_smoke` prompts also include ascension. No hidden controller starts a run. Verify the actual selection from screenshots. Only the explicitly selected `first_combat_smoke` prompt requests stopping after one combat; both existing gameplay prompts continue until victory or defeat.

Pass `-T game_seed=1` to request literal seed `1` in the game's seed field. This instruction is included in either gameplay prompt, and the requested seed is recorded in task/sample metadata and the sample ID. The AI must enter it through the game interface; setup does not inject a seed. Set `game_seed: null` in task arguments to omit the instruction and retain the prior unseeded sample ID. This parameter is separate from `generate_config.seed`, which controls model sampling and remains unset. A requested seed is not proof of the seed actually used: verify the visible seed after the run starts.

The `visual_agent` solver accepts `harness` (`react` or `codex`), `max_screenshots` (`3`), `tool_timeout` (`180` seconds), ReAct's `compaction_threshold` (`787500` tokens), and the `codex` settings described above. Codex has its own `codex.compaction_threshold` (`193800` tokens). The offline wiki file contains 750 pages with original article text and source URLs. See `THIRD_PARTY.md` for attribution. The vendored computer backend retains Inspect's MIT license. A small local availability check makes its browser actions return a recoverable tool error when Firefox ESR is absent, rather than timing out and aborting the sample.

Desktop argument-parsing failures are returned to the model as recoverable tool errors so it can correct the action. Empty calls/batches, malformed coordinates or zoom regions, wrong field types and missing required fields are checked before any action in a batch executes. Supplying coordinates to mouse-down/up returns guidance to move the cursor first; stock Inspect silently ignores those coordinates. Batched waits accept fractional seconds; negative and non-finite durations are rejected.

Wait and key-hold durations are seconds. A duration at or above the configured tool timeout is rejected immediately with unit guidance because it cannot finish within that timeout. With the default 180-second timeout, `duration: 3000` returns an error immediately rather than sleeping until the command times out. Setting `tool_timeout: null` retains unlimited-duration behavior.

Backend command timeouts also return tool errors. The timed-out command's process group is killed, and the model is told to check the screen before retrying because input may already have taken effect. This does not undo completed actions or make batches atomic: runtime errors can still occur partway through a valid batch. Unexpected backend failures, unavailable sandboxes and setup failures remain evaluation errors. Ordinary Bash/Python command failures already return their error output to the model.

## Submission and logs

The agent finishes with `submit(max_floor: int)`. Inspect stores the integer as the final completion and retains the tool call. This is an unverified self-report. The user checks screenshots to determine gameplay progress and whether the floor report is accurate. Ordinary shell/Python calls are recorded in the transcript. There is no grader or aggregate score.

Hawk's live viewer shows actions and screenshots when `log_realtime` is enabled. No local viewer or relay is required. Installation and sandbox failures remain errors rather than game losses.

## Slay the Spire 2

`sts_hawk/second_game` uses the owned Linux **v0.107.1** copy, defaults to Ironclad at **A10**, and asks for all three Acts with one run and no restart. It retains the integer max-floor submission and has no grader. Select `-T prompt_name=first_combat_smoke_sts2` to stop after one combat instead:

```bash
inspect eval sts_hawk/second_game --model openrouter/openai/gpt-6-luna \
  -M responses_api=true -M responses_store=false -S harness=react
```

Supply a separate private StS2 runtime archive through `STS_ASSET_URL`. The installer checks the version. Startup uses the built-in `--force-steam=off` switch, OpenGL, a null ALSA device and a 1280×800 desktop. No game assembly patch is required. The archive contains Workshop `UnlockTheSpire` v1.0.3; an unlocked profile can be included as `profile/` and copied into the isolated container. Mod activation and A10 availability must be verified before gameplay. Never publish the game archive or Steam authentication files.

An isolated profile can also be supplied as a base64-encoded tar.gz through the optional `STS_PROFILE_BASE64` runner secret. Its contents are applied over the archive's profile before launch. This keeps the game archive fixed while preparing and verifying the unlocked starting state. Keep this profile private too.

The Linux launcher preloads the system `libgcc_s.so.1` for the bundled Harmony 2.4.2 exception helper. Without it, mod initialization fails with `undefined symbol: _Unwind_RaiseException` even though the game reports the mod as loaded. This reproduces [Harmony issue 766](https://github.com/pardeike/Harmony/issues/766); the runtime setting preserves the frozen game assemblies rather than replacing Harmony with the newer release.

No offline StS2 wiki is currently included; this task does not advertise the first game's wiki to the StS2 agent. This is an additional difference from Epoch. The user deferred wiki integration for the initial gameplay smoke. The game crashes under local AMD64 Docker emulation on the ARM Mac; native AMD64 Hawk startup is verified at the main menu, with about 28 seconds to menu readiness. Unlock configuration and gameplay need separate verification. Use `sts_hawk/runtime_probe -T game=sts2 -T wait_seconds=90` for a no-inference startup check and game logs. The earlier 15-second capture was too early to establish readiness.

`runtime_probe` also accepts an operator-supplied `actions` list of stock computer calls and `capture_profile=true`. These run without model inference, retain screenshots in the transcript, and can export the isolated StS2 default profile as a compressed attachment in the private `.eval` log. This supports preparing and checking an unlocked starting profile; it does not add game-state tools or grading to the evaluated agent.

StS2 runtime probes wait for the game's complete-menu startup marker before issuing computer calls. Their diagnostic attachment includes cgroup CPU and memory counters and process memory/state alongside the game logs.

## Validation

Run `pytest tests`, `ruff check .` and `ruff format --check .`. Tests exercise the actual task setup, stock computer parser, Bash/Python execution, the installed wiki file, invalid and valid integer submissions, unscored completion, and setup-error propagation through mockllm. They also exercise the real Hawk Compose-to-Kubernetes conversion. External execution is simulated in local tests; the separate Linux runtime probe must establish actual game startup before the paid gameplay smoke.

Validate the real Docker runtime and tools locally with mockllm before launching on Hawk. Keep local containers bounded at two CPUs and 4 GB, reuse cached OS layers, mount the private archive read-only for installation, and remove the test containers afterwards. A scripted menu click, shell wiki search and Python file write/read verify integration, not model playing ability.

`STS_CODEX_DOCKER_TEST=1 pytest tests/test_codex.py` additionally uses the cached `local/sts-hawk-os:0.2.4` image and a blank X display, at one CPU and 1 GiB. It runs the real pinned Codex executable and Inspect model/MCP bridge with scripted inference, including native shell/Python, the wiki, screenshot retention, recoverable input errors, integer submission, voluntary exit and compaction. It does not start the game or make paid model calls. Install the optional Codex extra first; a missing cached OS image must be built from the runtime OS dependencies before this test.
