"""Expose the captured Epoch action schemas over the existing Inspect backend."""

import asyncio
import hashlib
import json
import math
import time
from collections import deque
from pathlib import Path

from inspect_ai.model import ContentImage, ContentText
from inspect_ai.tool import Tool, ToolDef, ToolError, ToolParams, memory, tool_with
from inspect_ai.util import store
from jsonschema import Draft7Validator

from sts_hawk import wiki_client
from sts_hawk.desktop import desktop_tool

SCHEMAS = json.loads(
    (Path(__file__).parent / "assets/epoch/sts2-tool-schemas.json").read_text()
)
STS1_SCHEMAS = json.loads(
    (Path(__file__).parent / "assets/epoch/sts1-tool-schemas.json").read_text()
)


def schema_tool(spec: dict, execute, model_input=None) -> Tool:
    """Bind a callable to the replay's explicit description and input schema."""
    validator = Draft7Validator(spec["parameters"])

    async def checked(**arguments):
        """Report malformed arguments to the model before running the tool."""
        error = next(validator.iter_errors(arguments), None)
        if error is not None:
            raise ToolError(error.message)
        return await execute(**arguments)

    result = ToolDef(
        tool=checked,
        name=spec["name"],
        description=spec["description"],
        parameters=ToolParams.model_validate(spec["parameters"]),
        parallel=False,
    ).as_tool()
    return (
        tool_with(result, model_input=model_input)
        if model_input is not None
        else result
    )


def epoch_tools(
    max_screenshots: int | None, timeout: int | None, height: int
) -> list[Tool]:
    """Build per-sample game actions, wiki references and persistent notes."""
    backend = desktop_tool(max_screenshots=None, timeout=timeout)
    if max_screenshots is not None and max_screenshots < 1:
        raise ValueError("max_screenshots must be positive or None.")
    recent = deque(maxlen=max_screenshots)
    last_image = None
    last_frame = None
    frame_number = 0

    def image_hash(image: ContentImage) -> str:
        """Identify a captured frame without retaining another copy of its image data."""
        return hashlib.sha256(image.image.encode()).hexdigest()

    def model_input(index, total, content, hints):
        """Retain a global image budget across all separate action tools."""
        if max_screenshots is None or isinstance(content, str):
            return content
        return [
            ContentText(
                text="Older screenshot removed; consult the latest game screenshots."
            )
            if isinstance(item, ContentImage)
            and (item.internal or {}).get("sts_frame") not in recent
            else item
            for item in content
        ]

    def publish(parts):
        """Assign distinct retained-frame identities even when screenshots are identical."""
        nonlocal frame_number
        result = []
        for item in parts:
            if isinstance(item, ContentImage):
                frame_number += 1
                if max_screenshots is not None:
                    recent.append(frame_number)
                item = item.model_copy(update={"internal": {"sts_frame": frame_number}})
            result.append(item)
        return result

    async def observe(action: dict, suppress_unchanged: bool, record: bool):
        """Execute one validated backend action and retain only changed frames."""
        nonlocal last_image, last_frame
        result = await backend(**action)
        parts = [ContentText(text=result)] if isinstance(result, str) else result
        images = [item for item in parts if isinstance(item, ContentImage)]
        if images:
            current = image_hash(images[-1])
            last_frame = images[-1]
            changed = current != last_image
            last_image = current
            if not changed and suppress_unchanged:
                return [ContentText(text="screen did NOT change")], False
        else:
            changed = False
            if any(getattr(item, "text", "") for item in parts):
                return parts, changed
        return publish(parts) if record else parts, changed

    def backend_action(name: str, arguments: dict) -> dict:
        """Translate pixel coordinates and key names into the stock Inspect API."""
        fields = {
            "left_click": ("x", "y"),
            "right_click": ("x", "y"),
            "mouse_move": ("x", "y"),
            "scroll": ("x", "y", "direction", "amount"),
            "left_click_drag": ("x1", "y1", "x2", "y2"),
            "key": ("keys",),
            "wait": ("seconds",),
            "screenshot": (),
        }
        if name not in fields:
            raise ToolError(f"Unsupported queued action: {name}")
        for field in fields[name]:
            value = arguments.get(field)
            expected = (
                str
                if field in {"keys", "direction"}
                else (int, float)
                if field == "seconds"
                else int
            )
            if (
                value is None
                or isinstance(value, bool)
                or not isinstance(value, expected)
            ):
                raise ToolError(f"{name} requires {field} with the correct type.")
        if name in {"left_click", "right_click", "mouse_move", "scroll"}:
            x, y = arguments["x"], arguments["y"]
            if not 0 <= x < 1280 or not 0 <= y < height:
                raise ToolError(
                    f"Coordinates must be inside the 1280x{height} game screen."
                )
            action = {"action": name, "coordinate": [x, y]}
            if name == "scroll":
                if arguments["direction"] not in {"up", "down", "left", "right"}:
                    raise ToolError("Scroll direction must be up, down, left or right.")
                if not 1 <= arguments["amount"] <= 30:
                    raise ToolError("Scroll amount must be between 1 and 30 ticks.")
                action.update(
                    scroll_direction=arguments["direction"],
                    scroll_amount=arguments["amount"],
                )
            return action
        if name == "left_click_drag":
            for x, y in [
                (arguments["x1"], arguments["y1"]),
                (arguments["x2"], arguments["y2"]),
            ]:
                if not 0 <= x < 1280 or not 0 <= y < height:
                    raise ToolError(
                        f"Drag coordinates must be inside the 1280x{height} game screen."
                    )
            return {
                "action": name,
                "start_coordinate": [arguments["x1"], arguments["y1"]],
                "coordinate": [arguments["x2"], arguments["y2"]],
            }
        if name == "key":
            return {"action": "key", "text": arguments["keys"]}
        if name == "wait":
            if (
                not math.isfinite(arguments["seconds"])
                or not 0 <= arguments["seconds"] <= 30
            ):
                raise ToolError("Queued wait seconds must be between 0 and 30.")
            return {"action": "wait", "duration": arguments["seconds"]}
        if name == "screenshot":
            return {"action": "screenshot"}
        raise ToolError(f"Unsupported queued action: {name}")

    def action_tool(spec: dict) -> Tool:
        """Create one action callable with the captured public schema."""
        name = spec["name"]

        async def execute(**arguments):
            """Run a game action, a bounded wait or a prevalidated action queue."""
            if name == "wait_for_change":
                duration = arguments["timeout"]
                if not math.isfinite(duration) or not 0 <= duration <= 30:
                    raise ToolError("timeout must be between 0 and 30 seconds.")
                deadline = time.monotonic() + duration
                while True:
                    result, changed = await observe(
                        {"action": "screenshot"}, True, True
                    )
                    if changed or time.monotonic() >= deadline:
                        return result
                    await asyncio.sleep(min(0.25, max(0, deadline - time.monotonic())))
            if name == "queue_actions":
                steps = arguments["steps"]
                if not steps or (height == 800 and len(steps) > 8):
                    raise ToolError(
                        "Provide at least one step; StS2 queues allow at most eight."
                    )
                actions = [backend_action(step["do"], step) for step in steps]
                # Validate the full batch before the first input can change the game.
                for action in actions:
                    if action["action"] == "wait" and not 0 <= action["duration"] <= 30:
                        raise ToolError("Queued wait seconds must be between 0 and 30.")
                logs = []
                result = []
                for index, action in enumerate(actions, 1):
                    result, changed = await observe(action, True, False)
                    logs.append(f"Step {index}: {action['action']}")
                    if not changed and action["action"] not in {"mouse_move", "wait"}:
                        logs.append(
                            f"screen did NOT change; skipped {len(actions) - index} remaining steps."
                        )
                        break
                if last_frame is not None:
                    result = [
                        item for item in result if not isinstance(item, ContentImage)
                    ] + [last_frame]
                return publish([ContentText(text="\n".join(logs)), *result])
            result, _ = await observe(
                backend_action(name, arguments), name != "screenshot", True
            )
            return result

        return schema_tool(spec, execute, model_input=model_input)

    tools = []
    for spec in STS1_SCHEMAS if height == 720 else SCHEMAS:
        name = spec["name"]
        if name == "memory":
            notes = memory(initial_data={"/memories/notes.md": ""})
            tools.append(schema_tool(spec, notes))
        elif name in {"wiki_search", "wiki_fetch"}:

            def wiki_tool(name: str, spec: dict) -> Tool:
                """Wrap wiki HTTP work without blocking the asynchronous agent loop."""

                async def execute(**arguments):
                    """Retrieve the requested wiki search or article."""
                    return await asyncio.to_thread(
                        getattr(wiki_client, name), **arguments
                    )

                return schema_tool(spec, execute)

            tools.append(wiki_tool(name, spec))
        elif name == "give_up":

            async def give_up(reason: str):
                """Record voluntary termination without inventing a floor or infrastructure error."""
                store().set("sts_give_up", {"reason": reason})
                return "Session ended by give_up."

            tools.append(schema_tool(spec, give_up))
        else:
            tools.append(action_tool(spec))
    return tools
