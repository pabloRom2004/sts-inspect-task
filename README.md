# Slay the Spire

An Inspect AI adaptation of [Epoch's SpireClimb](https://epoch.ai/benchmarks/spireclimb), using prompts and tool schemas recovered from supplied Epoch replays. StS1 targets Ascension 20 and the Heart. StS2 targets Ascension 10 and all three Acts.

The default task uses the captured game instructions, wiki-only search/fetch, persistent per-run notes and the replay action interface. This is an independent implementation with an integer floor self-report and no grader. It does not produce an official SpireClimb score. See [reproduction limits](docs/replay-parity.md).

## Usage

### Installation

```bash
pip install -e '.[dev]'
```

Supply the licensed Linux game, mods and an unlocked profile privately through `STS_ASSET_URL`. The StS1 and StS2 archives are separate. Supply `TAVILY_API_KEY` privately to the runner, which performs wiki requests. It is not sent into the game sandbox or stored in task code. Local development can read `~/.config/tavily/api-key` instead.

### Running evaluations

These commands start one full game with model-controlled character, ascension and seed selection:

```bash
inspect eval sts_hawk/first_combat --model openrouter/openai/gpt-6-luna \
  -M responses_api=true -M responses_store=false

inspect eval sts_hawk/second_game --model openrouter/openai/gpt-6-luna \
  -M responses_api=true -M responses_store=false
```

`first_combat` is the retained entrypoint name; its new default prompt plays a complete game. The StS1 prompt is captured verbatim apart from character, ascension and seed parameters. For StS2, the model selects Singleplayer → Custom, enters the seed and leaves modifiers off. No script starts or pre-seeds either game.

Do not launch a performance batch until the game version, unlocked content, visible seed/difficulty and startup state are verified. StS1 must offer the full Neow bonus. StS2 startup and combat remain a separate runtime integration check.

### Configurations

[default.yaml](src/sts_hawk/run_configs/default.yaml) owns built-in defaults. Prompts are named objects in `prompts.py`; message bodies and captured schemas are packaged under `assets/epoch/`. The replay profile uses summary compaction at 300,000 tokens, matching the supplied plans, and retains screenshots until compaction by default, as observed in the complete Epoch replay. Set `max_screenshots` explicitly only for a verified provider image limit.

[original.yaml](src/sts_hawk/run_configs/original.yaml) retains the replay-derived seven API retries. The maintained default permits 140 retries, as requested for provider outages. This original profile contains necessary local environment adaptations; the replay headers do not expose Epoch's complete implementation. Captured settings and remaining differences are recorded in the parity document. The published methodology now describes `CompactionAuto`, while these replays explicitly configured summary compaction.

For the previous minimal task, select `-T prompt_name=beat_game` or `first_combat`. `tool_profile=auto` selects its original desktop/shell/Python tools and offline wiki. The earlier `first_combat_smoke` and `first_combat_smoke_sts2` prompts remain available. Historical CLI adapter details are preserved in [the legacy reference](docs/legacy-task.md); that adapter is not Codex Desktop's native computer-use backend.

## Environment

The model interacts with a 1280×720 StS1 or 1280×800 StS2 X11 desktop in Docker, adapted to Kubernetes on Hawk. Licensed assets, profiles and credentials stay private. `prepare_game` installs the game before the interchangeable solver executes.

The StS2 runtime preserves frozen v0.107.1 assemblies and accepts private profile/mod overlays through `STS_PROFILE_BASE64` and `STS_RUNTIME_OVERLAY_BASE64`. Its `frame_rate_limit` defaults to 60. Existing `runtime_probe` and `manual_session` entrypoints remain available for no-model startup diagnosis and human play. The human viewer uses noVNC and an authenticated proxy inside the game sandbox. On Hawk, `browser_tunnel_enabled=true` starts the verified cloudflared tunnel; supply a private `STS_MANUAL_ACCESS_TOKEN` of at least 32 characters. The access key is exchanged for an HTTP-only cookie. `POST /api/finish` ends the manual session and cleans up its sandbox.

## Parameters

`first_combat` defaults to `character=IRONCLAD`, `ascension=20`, `game_seed='1'` and `prompt_name=epoch_sts1`. `second_game` defaults to Ascension 10 and `prompt_name=epoch_sts2`. Both retain setup timeout 900 seconds, command timeout 180 seconds and sandbox image `ubuntu:24.04`. Both game sandboxes default to 6 CPUs and Compose memory `12G`, with `processor_count=6` and `renderer_threads=3`; StS1 uses `java_heap_mb=4608`. These are user-selected allocations, separate from Hawk runner memory, and can be overridden through the task parameters.

The seed is the literal string the model types into the game. It is separate from model sampling, which remains unseeded. Replay prompts require an explicit game seed; legacy prompts still support `game_seed=None`.

`visual_agent` uses `tool_profile=auto`, no fixed screenshot cap, a 180-second tool timeout and a 300,000-token compaction threshold. `epoch` and `standard` select the tool profiles explicitly. The replay profile exposes `screenshot`, `left_click`, `right_click`, `left_click_drag`, `mouse_move`, `key`, `scroll`, `wait_for_change`, `queue_actions`, `memory`, `wiki_search`, `wiki_fetch`, `give_up` and `submit`.

Default generation uses `max` reasoning and a 128,000-token maximum response. There is one epoch, a 40,000-message limit, a 240,000-second time limit and no cumulative token cap. The time limit approximates the replay setup’s 4,000-minute wall deadline through Inspect’s clock. API requests permit 140 retries with Inspect’s exponential backoff; the original replay-derived profile uses seven. The connection ceiling is 24, as in the captured Luna header. No automatic restart is performed. Select another model deliberately and verify its provider limits before launching.

## Scoring and logs

`submit(max_floor: int)` ends the sample and records an unverified integer. There is no grader or aggregate score. Confirm terminal outcome and floor from screenshots separately. Invalid tool arguments, rejected wiki addresses and expected network/input errors are returned to the model; setup, sandbox and unexpected programming failures remain evaluation errors.

Hawk's viewer can display live actions and screenshots. Keep repository `logs/` flat with only `.eval` files; put supporting files in `run-artifacts/<run-name>/`.

## Validation

```bash
pytest tests
ruff check .
ruff format --check .
```

The tests run both task factories through mock inference, real tool parsing, wiki response formatting, persistent notes, malformed inputs, queue aborts and optional provider-specific image pruning, including repeated identical screenshots.

For a bounded Docker/X11 transport test using the existing cached OS image:

```bash
STS_EPOCH_DOCKER_TEST=1 pytest tests/test_epoch_docker.py
```

This uses one CPU and 1 GiB, makes no paid model requests and starts no game. It establishes desktop transport, not gameplay or benchmark equivalence. Validate actual game startup before a paid gameplay smoke, then retain the review gate before a full batch.
