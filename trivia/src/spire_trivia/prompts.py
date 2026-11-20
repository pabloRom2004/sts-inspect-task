"""Named prompts for unaided, single-turn knowledge recall."""

SYSTEM_MESSAGES = {
    "knowledge_only": (
        "Answer this Slay the Spire trivia question using only your existing knowledge. "
        "Do not use tools, search, or external resources. Select exactly one of the eight choices. "
        "Your entire final response must be a single uppercase letter: A, B, C, D, E, F, G, or H. "
        "Do not include an explanation, punctuation, or any other text."
    )
}

SYSTEM_MESSAGES["knowledge_abstention"] = (
    "Answer this Slay the Spire trivia question using only your existing knowledge. Do not use tools, search, or external resources. Select exactly one of the nine choices. A correct answer scores +1, an incorrect answer scores -1, and I (I don't know) scores 0. You may choose I to abstain. Malformed responses score -1. Your entire final response must be a single uppercase letter: A, B, C, D, E, F, G, H, or I. Do not include an explanation, punctuation, or any other text."
)

SYSTEM_MESSAGES["knowledge_abstention_explicit"] = (
    "Answer this Slay the Spire trivia question using only your existing knowledge. Do not use tools, search, or external resources. Select exactly one of the nine choices. A correct answer scores +1, an incorrect answer scores −1, and I don’t know scores 0. Your entire final response must be a single uppercase letter: A, B, C, D, E, F, G, H, or I. Do not include an explanation, punctuation, or any other text."
)
