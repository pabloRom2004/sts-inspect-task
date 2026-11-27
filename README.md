# Spire Trivia

[Play the quiz](https://pablorom2004.github.io/sts-inspect-task/) · [Question bank](data/questions.json) · [Answer key](data/answer-key.json)

A single-screen quiz using the SpireClimb audit’s corrected **text200-v7** set. There are 100 questions per game about cards, relics, monsters, potions, events and mechanics. Slay the Spire 1 uses the unmodded desktop game. Slay the Spire 2 targets **v0.107.1**, released 19 June 2026 UTC.

Each question has eight possible answers and an “I don’t know” option. A correct choice earns one point, a wrong choice costs one, and passing scores zero. The score is separate for each game. You can revisit questions with the arrows. Your first answer counts, and progress is saved in this browser. On short screens, the option arrows let you read every answer without scrolling. On a keyboard, use A–I to answer and the left/right arrows to move between questions.

The site loads the JSON bank directly. Each item includes its stable ID, original prompt, choices, correct letter, explanation, and source. The versioned question and answer files here are identical to the ones used for the corrected audit question set. The original [evaluation task](https://github.com/pabloRom2004/sts-inspect-task/tree/codex/trivia-v01071/trivia) is in the same repository.

To run locally, serve this branch with `python3 -m http.server 8000` and open `http://localhost:8000`. GitHub Pages serves the root of the `gh-pages` branch.

## Credits and licence

The quiz code and original quiz material in this branch are available under the [MIT License](LICENSE). Slay the Spire and its sequel are by Mega Crit. Game artwork and quoted in-game text belong to their respective owners. [Art credits](art/README.md) list the source for each illustration. DM Sans and Spectral are distributed under the SIL Open Font License in [fonts](fonts/).
