"""Named prompts for unaided, single-turn knowledge recall."""

SYSTEM_MESSAGES = {
    "knowledge_only": (
        "Answer this Slay the Spire trivia question using only your existing knowledge. "
        "Do not use tools, search, or external resources. Select exactly one of the eight choices. "
        "Your entire final response must be a single uppercase letter: A, B, C, D, E, F, G, or H. "
        "Do not include an explanation, punctuation, or any other text."
    )
}
