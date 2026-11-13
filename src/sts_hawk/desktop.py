"""Validate desktop actions before passing them to Inspect's computer tool."""

import math
from functools import wraps

from inspect_ai.tool import Tool, ToolDef, ToolError, ToolResult, computer, tool_with
from jsonschema import Draft7Validator


def desktop_tool(max_screenshots: int | None, timeout: int | None) -> Tool:
    """Keep stock desktop behavior while rejecting malformed actions recoverably."""
    stock = computer(max_screenshots=max_screenshots, timeout=timeout)
    schema = ToolDef(stock).parameters.model_dump(exclude_none=True)
    schema["properties"].pop("actions")
    schema["required"] = ["action"]
    schema["properties"]["duration"] = {"type": ["number", "null"], "minimum": 0}
    for field, size in [("coordinate", 2), ("start_coordinate", 2), ("region", 4)]:
        schema["properties"][field] = {
            "type": ["array", "null"],
            "items": {"type": "integer"},
            "minItems": size,
            "maxItems": size,
        }
    validator = Draft7Validator(schema)

    @wraps(stock)
    async def execute(**kwargs) -> ToolResult:
        """Validate the entire batch before executing any of its actions."""
        actions = kwargs.get("actions")
        if actions is not None:
            if any(
                value is not None for key, value in kwargs.items() if key != "actions"
            ):
                raise ToolError(
                    "Provide either one action or an actions list, not both."
                )
            if not isinstance(actions, list) or not actions:
                raise ToolError("actions must be a non-empty list of action objects.")
        else:
            actions = [
                {key: value for key, value in kwargs.items() if key != "actions"}
            ]
        for index, action in enumerate(actions, start=1):
            validate_action(action, validator, index)
        return await stock(**kwargs)

    return tool_with(execute, name="desktop")


def validate_action(action: object, validator: Draft7Validator, index: int) -> None:
    """Return actionable errors for malformed fields and action-specific requirements."""
    error = next(validator.iter_errors(action), None)
    if error is not None:
        field = ".".join(str(part) for part in error.path) or "action"
        raise ToolError(f"Action {index}, {field}: {error.message}")
    required = {
        "key": ("text",),
        "hold_key": ("text", "duration"),
        "type": ("text",),
        "mouse_move": ("coordinate",),
        "left_click_drag": ("start_coordinate", "coordinate"),
        "scroll": ("scroll_amount", "scroll_direction"),
        "wait": ("duration",),
        "zoom": ("region",),
        "navigate": ("text",),
    }
    for field in ("action", *required.get(action.get("action"), ())):
        if action.get(field) is None:
            raise ToolError(f"Action {index}: {field} must be provided.")
    duration = action.get("duration")
    if isinstance(duration, float) and not math.isfinite(duration):
        raise ToolError(f"Action {index}: duration must be finite.")
    if (
        action["action"] in ("left_mouse_down", "left_mouse_up")
        and action.get("coordinate") is not None
    ):
        raise ToolError(
            f"Action {index}: {action['action']} acts at the current cursor; "
            "use mouse_move first and omit coordinate from this action."
        )
