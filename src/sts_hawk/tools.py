from inspect_ai.tool import Tool, tool


@tool
def submit_floor() -> Tool:
    """Create the unverified integer floor-reporting tool."""

    async def execute(max_floor: int) -> str:
        """Finish the run by reporting the maximum floor reached.

        Args:
            max_floor: The maximum floor number you reached during this run.
        """
        return str(max_floor)

    return execute
