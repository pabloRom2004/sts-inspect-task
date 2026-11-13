"""Backport Inspect 0.3.289's tool-message count fix to Hawk's pinned build.

The resolver below is copied from Inspect AI (MIT); see THIRD_PARTY.md.
Remove this module when Hawk upgrades. Newer versions use their own resolver.
"""

import inspect_ai
import inspect_ai.model._model as inspect_model
from inspect_ai.model import ChatMessage, ChatMessageTool
from inspect_ai.tool import ToolDef
from inspect_ai.tool._tool_call import ToolCallModelInputHints
from shortuuid import uuid


def apply_hawk_image_counter_fix() -> None:
    """Install the upstream fix only on the verified affected Hawk version."""
    if inspect_ai.__version__ == "0.3.286.dev10+g3a44082ca":
        inspect_model.resolve_tool_model_input = resolve_tool_model_input


def resolve_tool_model_input(
    tdefs: list[ToolDef], messages: list[ChatMessage], hints: ToolCallModelInputHints
) -> list[ChatMessage]:
    """Apply tool input handlers using each tool's own message count."""
    # filter on tooldefs that have a model input handler
    tdefs = [tdef for tdef in tdefs if tdef.model_input is not None]

    # bail if there are no handlers
    if len(tdefs) == 0:
        return messages

    # don't mutate the original messages
    messages = [m.model_copy() for m in messages]

    # extract tool messages
    tool_messages = [
        message for message in messages if isinstance(message, ChatMessageTool)
    ]
    # run model_input handlers over all tool_messages with the same function name
    for tdef in tdefs:
        assert tdef.model_input
        # filter messages down to just this tool
        tdef_tool_messages = [
            message for message in tool_messages if message.function == tdef.name
        ]
        # call the function for each tool, passing the index, total, and content
        for index, message in enumerate(tdef_tool_messages):
            model_input_content = tdef.model_input(
                index, len(tdef_tool_messages), message.content, hints
            )
            if model_input_content is not message.content:
                message.content = model_input_content
                message.id = uuid()

    # return modified messages
    return messages
