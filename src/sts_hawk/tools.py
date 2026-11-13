import re
from functools import cache
from pathlib import Path

from inspect_ai.tool import Tool, tool

from sts_hawk.state import RunState, WikiRead


@cache
def wiki_articles() -> dict[str, str]:
    """Split the copied wiki using its article delimiters, preserving source URLs."""
    text = (Path(__file__).parent / "assets/wiki.md").read_text()
    pages = re.split(r"\n---\n\s*\n# ", text)[1:]
    return {page.split("\n", 1)[0].strip(): "# " + page for page in pages}


def normalized(text: str) -> str:
    """Normalize article queries without changing the returned source text."""
    return re.sub(r"[^a-z0-9]", "", text.lower())


@tool
def wiki() -> Tool:
    """Provide article lookup over the local Slay the Spire wiki."""

    async def execute(query: str) -> str:
        """Read a wiki article by title, or search titles and article contents.

        Args:
            query: Enemy or other article title to read, or a search phrase.
        """
        key = normalized(query)
        if not key:
            return "Enter an enemy name, article title, or search phrase."
        articles = wiki_articles()
        exact = next((title for title in articles if normalized(title) == key), None)
        if exact is None:
            titles = [title for title in articles if key in normalized(title)]
            if len(titles) == 1:
                exact = titles[0]
            else:
                if not titles:
                    titles = [
                        title
                        for title, body in articles.items()
                        if query.lower() in body.lower()
                    ]
                return "Matching article titles:\n" + "\n".join(titles)
        history = RunState()
        history.wiki_reads = history.wiki_reads + [
            WikiRead(
                title=exact,
                before_victory=not history.won,
                enemies_present=history.first_enemies,
            )
        ]
        return articles[exact]

    return execute
