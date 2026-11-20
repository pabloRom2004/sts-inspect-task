# Spire Trivia

Two separate text-only benchmarks of 100 independent questions each for Slay the Spire 1 and 2. The maintained `text200-v5` revision asks only about new StS2 cards, enemies, relics, potions, events and mechanics. Each question has eight factual choices A–H plus I (I don't know). Generic move matching is removed in both games; each has 55 numerical questions. The Gold-Plated Cables effect question is retained.

Each game contains 50 card questions, 15 relic questions, 15 enemy questions, 10 potion questions, 5 event questions and 5 mechanics questions. StS2 mechanics cover Eternal, Sly, Doom, Clone and Imbued. Data is pinned to [Spire Archive](https://github.com/nkhoit/spire-archive/tree/4e6b0e040ccd00eb04fb1ab7fb0b298c222d2f29); StS2 uses v0.107.1. Cards are unupgraded and enemy damage is at Ascension 0 before modifiers.

StS2 facts are scraped from exact Slay the Spire Wiki revisions saved on 20 November 2026. New cards for existing characters are eligible after individual review; returning content, simple renames and numerical retunes are excluded. Novelty checks cover the full first-game catalog. `data/sts2-wiki-novelty-audit.json` records each new-content reason, and `data/text200-v5-protocol.json` records page revisions and selection rules. The snapshot excludes pages marked Beta content. Selection did not use model results.

## Usage

### Installation

```bash
uv pip install -e '.[dev]'
```

### Local validation

```bash
inspect eval spire_trivia/trivia --model mockllm/model --limit 2 --log-dir ../../logs
inspect eval spire_trivia/trivia -T game=sts2 -T smoke=true --model mockllm/model --log-dir ../../logs
```

Each sample makes one generation call without tools, search, examples, prior answers or images. No game installation, Docker image or GPU is needed. Real-model evaluations belong on Hawk using the designated work billing route. Require a bounded successful Hawk smoke with the intended model, settings, prompts and scorer before a full run. A settings preference does not authorize adding models. Use explicit `game=sts1` and `game=sts2` filters and always report the two benchmarks separately.

### Configurations and historical reproduction

`src/spire_trivia/run_configs/default.yaml` owns the complete maintained v4 configuration, including `knowledge_abstention_explicit`, `abstention_letter`, and medium reasoning. `original.yaml` selects the original artwork-inclusive bank and strict eight-letter scoring. The original 0.1.0 runtime remains pinned at commit `6dc20362e0ebe1177eb4397b8ed8d170fd98af9e`.

```bash
inspect eval spire_trivia/trivia --run-config src/spire_trivia/run_configs/default.yaml --model mockllm/model --limit 2 --log-dir ../../logs
inspect eval spire_trivia/trivia -T question_set=text200-v3 -T system_prompt=knowledge_abstention -T scorer=abstention_letter --model mockllm/model --limit 2 --log-dir ../../logs
inspect eval spire_trivia/trivia -T question_set=text200-v2 -T system_prompt=knowledge_only -T scorer=strict_letter --model mockllm/model --limit 2 --log-dir ../../logs
```

The earlier banks and results remain frozen. V1 (`text200`) replaced artwork with text. V2 replaced the vague Block definition with Artifact. V3 introduced I and negative scoring. V4 replaces the full StS2 bank with new-content-only questions and uses the user's exact scoring sentence; it adds no confidence or guessing advice. Earlier results are not v4 results. Each independent question has a single-turn context, so no compaction is used.

## Options and parameters

Inspect's `--sample-id`, `--sample-shuffle`, `--epochs` and `--limit` controls are supported. The YAML owns solver and generation defaults; runtime overrides remain available. Extra-tool or multi-turn runs require separate reporting.

- `question_set`: `text200-v5` by default. Historical choices include `text200-v4`, `text200-v3`, `text200-v2`, `text200`, `text100` and `all200`.
- `game`: `sts1`, `sts2`, or null for both.
- `category`: `cards`, `relics`, `monsters`, `potions`, `events`, `mechanics`, or null.
- `question_kind`: a participant format key or null.
- `include_images`: false by default. All maintained text banks have no images.
- `sample_ids`: optional IDs from the selected bank.
- `smoke`: false by default; true selects one question per topic and game before other filters.
- `system_prompt`: `knowledge_abstention_explicit` for v4, `knowledge_abstention` for v3, or `knowledge_only` for earlier banks.
- `scorer`: `abstention_letter` for v3/v4, `strict_letter` for earlier banks.

Filters compose by intersection. Mismatched protocol/prompt/scorer combinations, unknown IDs and empty intersections fail before inference. The default is one epoch; runtime overrides use the configured mean reducer.

## Scoring

A correct answer scores +1, an incorrect answer scores −1, and I don’t know scores 0.

That sentence appears verbatim in the model prompt. The entire trimmed final response must be one uppercase A–I letter. Malformed replies score −1. Provider failures and limits remain unscored and are never treated as abstentions. Inspect averages `net_score`; reports also show per-game total points out of 100, correct/wrong/abstained/invalid counts, coverage and accuracy among answered valid questions. Historical strict scoring accepts only A–H and preserves its original accuracy/format outputs.

The participant bank contains no reference answers or source metadata. Answer keys are loaded host-side into `Sample.target`. The separate browser viewer intentionally includes answers and reference artwork. This is an unofficial research benchmark; game content belongs to Mega Crit. Multiple-choice performance does not by itself establish literal training-data memorization.
