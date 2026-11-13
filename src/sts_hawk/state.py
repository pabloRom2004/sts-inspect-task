from inspect_ai.util import StoreModel
from pydantic import Field


class WikiHistory(StoreModel):
    """Record the wiki articles actually returned to the agent."""

    titles: list[str] = Field(default_factory=list)
