# Spire Trivia

100 independent, text-only, eight-choice questions about Slay the Spire 1 and 2, selected from the original 200-question bank. Each game has 24 card questions, 8 relic questions, 8 enemy questions, 4 potion questions, 2 event questions, and 4 mechanics questions. Cards cover matching in both directions and numerical recall. No images are supplied by default.

Data comes from [Spire Archive](https://github.com/nkhoit/spire-archive) at commit `4e6b0e0`; StS2 text uses its v0.107.1 history. Cards are unupgraded, and enemy attack values use Ascension 0 before modifiers. The frozen IDs and selection protocol are in `data/text100-selection.json`. Selection uses a fixed seed, category/format quotas, and answer-position balance, without model outputs. All prompts and choices are unchanged from the original bank. There are 50 questions per game and twelve or thirteen correct answers per letter overall.

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

Real-model runs belong on Hawk with the designated work billing route. The default selects all 100 fixed text questions. `smoke=true` selects 12 of those, one per topic and game. Each sample makes one generation call and includes only a question and eight choices. No tools, lookup, examples, or prior questions are supplied. Every model should receive the same frozen question set.

### Configurations

`src/spire_trivia/run_configs/default.yaml` owns the maintained 100-question text-only defaults. `original.yaml` explicitly selects the historical 200-question bank with artwork. It preserves that bank's prompts, choices, and scoring settings; the original version 0.1.0 runtime is pinned at commit `6dc20362e0ebe1177eb4397b8ed8d170fd98af9e`. The archive configuration is for requested historical reproduction; future runs use the text-only default.

```bash
inspect eval spire_trivia/trivia --run-config src/spire_trivia/run_configs/default.yaml --model mockllm/model --limit 2 --log-dir ../../logs
```

The first full Luna run remains at the original 200-question commit and continues unchanged. Its scores on the selected 100 can be reported as a subset of that run, without representing them as a new 100-question inference run. Models, reasoning effort, full response allowance, concurrency, and sample ceilings are explicit in Hawk run artifacts. This independent one-turn task does not accumulate conversation history or use compaction.

## Environment

No game installation, Docker image, GPU, or sandbox is needed. Historical artwork remains bundled solely for explicit archive reproduction; the default 100-question inputs contain no images. Game content belongs to Mega Crit, and this is an unofficial research benchmark.

## Options

Inspect's `--sample-id`, `--sample-shuffle`, `--epochs`, and `--limit` controls select and repeat samples. `--solver` can replace native `generate(tool_calls="none")`; extra-tool or multi-turn runs should be reported separately.

## Parameters

- `question_set`: `text100` by default; `all200` selects the original bank before other filters.
- `game`: `sts1`, `sts2`, or null for both.
- `category`: `cards`, `relics`, `monsters`, `potions`, `events`, `mechanics`, or null.
- `question_kind`: a format key in the participant records, or null.
- `include_images`: false by default; the text100 set has no images regardless of this flag.
- `sample_ids`: optional list of IDs from the selected set.
- `smoke`: false by default; true selects 12 representative questions from the selected set.
- `system_prompt`: `knowledge_only` by default.
- `scorer`: `strict_letter` by default.

Filters combine by intersection. Unknown IDs and empty intersections fail before inference. The default is one epoch; runtime overrides are honored with the mean reducer.

## Scoring

After trimming surrounding whitespace, the entire final response must be one uppercase A–H letter. `accuracy` is one only for the exact correct letter. `format` is one for any valid A–H letter, including a wrong choice. Explanations, lowercase, punctuation, multiple letters, empty output, and prose refusals fail the format requirement. Infrastructure failures remain Inspect errors and are reported separately from incorrect answers. There is no model judge or partial credit. Uniform chance accuracy is 12.5%.

The participant bank contains no reference answers or source metadata. The host loads keys into `Sample.target`. The browser artifact intentionally includes answers for review and is separate from model input. Prompts in the 100-question protocol are byte-for-byte unchanged from the original bank's corresponding participant inputs.
