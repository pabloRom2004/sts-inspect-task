# Spire Trivia

200 independent, eight-choice questions about Slay the Spire 1 and 2, built from [Spire Archive](https://github.com/nkhoit/spire-archive) at commit `4e6b0e0`. Each game has 50 card questions, 15 relic questions, 15 enemy questions, 10 potion questions, 5 event questions, and 5 mechanics questions. The StS2 text is pinned to the archive's v0.107.1 history. All cards are unupgraded; enemy attack values use Ascension 0 before modifiers.

The task measures unaided multiple-choice knowledge recall. Performance alone cannot establish literal training-data memorization or separate recognition from inference. Artwork is a separate 20-question slice, and paired text facts may appear among distractors, so it is useful to report results by format and game. No claims of difficulty calibration or full manual verification are made.

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

Real-model runs belong on Hawk with the designated work billing route. `smoke=true` selects the same 12 fixed questions for every model, one per game and topic, including two image questions and two enemy-number questions. Omit it for all 200. Models receive only the question, eight choices, and the image when applicable. Images are inline PNG data with no revealing filenames or alt text. No model-facing tools, external lookup, examples, or prior questions are supplied. Each sample makes one generation call.

### Configurations

`src/spire_trivia/run_configs/default.yaml` owns the maintained task, solver, generation, and epoch defaults. This is a new benchmark without an upstream original configuration. No duplicate `original.yaml` is needed. The model, reasoning effort, full response allowance, concurrency, and smoke ceilings are chosen explicitly in the Hawk run artifacts. There is no compaction in this independent one-turn task; histories never accumulate between questions.

```bash
inspect eval spire_trivia/trivia --run-config src/spire_trivia/run_configs/default.yaml --model mockllm/model --limit 2 --log-dir ../../logs
```

## Environment

There is no game installation, Docker image, GPU, or sandbox. The package bundles the 20 selected card illustrations and source-derived question records. Game content and artwork belong to Mega Crit; the source project's software licensing does not transfer ownership of game assets. This is an unofficial research benchmark.

## Options

Use Inspect's `--sample-id`, `--sample-shuffle`, `--epochs`, or `--limit` controls to select and repeat questions. `--solver` can replace the default native `generate(tool_calls="none")` solver; runs using extra tools or multiple turns should be reported separately.

## Parameters

- `game`: `sts1`, `sts2`, or null for both.
- `category`: `cards`, `relics`, `monsters`, `potions`, `events`, `mechanics`, or null.
- `question_kind`: one of the six format keys in the participant records, or null.
- `include_images`: true by default; false removes 20 image questions.
- `sample_ids`: optional list of stable question IDs; unknown IDs raise an error.
- `smoke`: false by default; true selects 12 representative wiring samples.
- `system_prompt`: `knowledge_only` by default.
- `scorer`: `strict_letter` by default.

Filters combine by intersection. An empty intersection fails before inference. The default is one epoch; runtime epoch overrides are honored and repeated scores use the mean reducer.

## Scoring

The final response must contain exactly one uppercase A–H letter after trimming surrounding whitespace. `accuracy` is one only for the exact correct letter. `format` is one for any valid A–H letter, including a wrong answer. Explanations, lowercase letters, punctuation, multiple letters, empty output, and prose refusals fail both unless the final completion itself meets the contract. Infrastructure errors remain Inspect errors. There is no model judge or partial credit. All 200 correct-answer positions are balanced at 25 per letter; chance accuracy is 12.5%.

The participant JSONL contains no reference answers or entity names outside the question and options. The answer key is loaded only into host-side `Sample.target`. The manifest records source and asset hashes. The browser review artifact intentionally includes answers for inspection and is separate from participant input.
