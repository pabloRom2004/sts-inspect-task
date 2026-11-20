# Spire Trivia

200 independent, text-only, eight-choice questions about Slay the Spire 1 and 2. Each game has 50 card questions, 15 relic questions, 15 enemy questions, 10 potion questions, 5 event questions, and 5 mechanics questions. Cards cover matching in both directions and numerical recall. No images are supplied by default.

Data comes from [Spire Archive](https://github.com/nkhoit/spire-archive) at commit `4e6b0e0`; StS2 uses v0.107.1. Cards are unupgraded, and enemy attack values use Ascension 0 before modifiers. `data/text200-v2-protocol.json` records the current revision. It replaces the vague Block item `sts1-096` with a different Artifact question `sts1-111`, preserving the other 199 participant records from v1. `data/text200-protocol.json` retains v1 and its original 20 artwork-to-text replacements. There are 100 questions per game and 25 correct answers per letter overall.

This measures unaided multiple-choice knowledge recall. Accuracy cannot by itself establish literal training-data memorization or distinguish recognition from inference. This is a source-backed first version rather than a claim of expert certification of every source value.

## Usage

### Installation

```bash
uv pip install -e '.[dev]'
```

### Running evaluations

```bash
inspect eval spire_trivia/trivia --model mockllm/model --limit 2 --log-dir ../../logs
inspect eval spire_trivia/trivia -T smoke=true --model openrouter/openai/gpt-6-luna --log-dir ../../logs
```

Real-model runs belong on Hawk with the designated work billing route. The default selects all 200 fixed text questions. `smoke=true` selects 12 of those, one per topic and game. Each sample makes one generation call and includes only a question and eight choices. No tools, lookup, examples, or prior questions are supplied. Every model should receive the same frozen question set.

### Configurations

`src/spire_trivia/run_configs/default.yaml` owns the maintained 200-question text-only defaults. `original.yaml` explicitly selects the historical 200-question bank with artwork. It preserves that bank's prompts, choices, and scoring settings; the original version 0.1.0 runtime is pinned at commit `6dc20362e0ebe1177eb4397b8ed8d170fd98af9e`. The archive configuration is for requested historical reproduction; future runs use the text-only default.

```bash
inspect eval spire_trivia/trivia --run-config src/spire_trivia/run_configs/default.yaml --model mockllm/model --limit 2 --log-dir ../../logs
```

The completed full Luna text-only run used v1 (`text200`), pinned at commit `7cdb2941af384dbd71fa4579a1f1c34945faf077`. Its recorded score is unchanged; the v2 replacement has not been evaluated on Luna. The earlier artwork-inclusive run remains separate. Models, reasoning effort, response allowance, concurrency, and sample ceilings are explicit in Hawk artifacts. Each question has an independent one-turn context, so no compaction is used.

## Environment

No game installation, Docker image, GPU, or sandbox is needed. Historical artwork remains bundled solely for explicit archive reproduction; the default 200-question inputs contain no images. Game content belongs to Mega Crit, and this is an unofficial research benchmark.

## Options

Inspect's `--sample-id`, `--sample-shuffle`, `--epochs`, and `--limit` controls select and repeat samples. `--solver` can replace native `generate(tool_calls="none")`; extra-tool or multi-turn runs should be reported separately.

## Parameters

- `question_set`: `text200-v2` by default; `text200` reproduces v1, including the retired question; `text100` selects the superseded fixed text subset; `all200` selects the original bank before other filters.
- `game`: `sts1`, `sts2`, or null for both.
- `category`: `cards`, `relics`, `monsters`, `potions`, `events`, `mechanics`, or null.
- `question_kind`: a format key in the participant records, or null.
- `include_images`: false by default; the text200 and text100 sets have no images regardless of this flag.
- `sample_ids`: optional list of IDs from the selected set.
- `smoke`: false by default; true selects 12 representative questions from the selected set.
- `system_prompt`: `knowledge_only` by default.
- `scorer`: `strict_letter` by default.

Filters combine by intersection. Unknown IDs and empty intersections fail before inference. The default is one epoch; runtime overrides are honored with the mean reducer.

## Scoring

After trimming surrounding whitespace, the entire final response must be one uppercase A–H letter. `accuracy` is one only for the exact correct letter. `format` is one for any valid A–H letter, including a wrong choice. Explanations, lowercase, punctuation, multiple letters, empty output, and prose refusals fail the format requirement. Infrastructure failures remain Inspect errors and are reported separately from incorrect answers. There is no model judge or partial credit. Uniform chance accuracy is 12.5%.

The participant bank contains no reference answers or source metadata. The host loads keys into `Sample.target`. The browser artifact intentionally includes answers for review and is separate from model input. The v2 set preserves 199 participant inputs from v1 byte-for-byte and gives its one replacement a new ID. Historical inputs and answer keys remain separately available.
