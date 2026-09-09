"""Tool call execution: running a bound tool and reporting the result."""

import re
from typing import Any, AsyncGenerator, Dict, List

from services.graph.events import EventType, create_event


def _extract_missing_fields(error: str) -> List[str]:
    """Extract missing field names from a Pydantic validation error string."""
    # Pydantic v2 format: "X validation error(s)...\nfield_name\n  Field required..."
    fields = re.findall(r"(\w+)\s*\n\s*(?:Field required|field required)", error)
    if not fields:
        # Pydantic v1 format: "field required (type=value_error.missing)" with "loc": ("field_name",)
        fields = re.findall(r"'loc':\s*\('(\w+)',?\)", error)
    return fields


async def execute_tool_call(tool_call: dict, tools: List[Any]) -> str:
    """Execute a tool call and return the result."""
    tool_name = tool_call.get("name")
    tool_args = tool_call.get("args", {})

    # Find and execute the tool
    for tool in tools:
        if tool.name == tool_name:
            try:
                result = await tool.ainvoke(tool_args)
                return result
            except Exception as e:
                error = str(e)
                if "field required" in error.lower() or "validation error" in error.lower():
                    # Extract specific missing field names from Pydantic errors
                    missing_fields = _extract_missing_fields(error)
                    if missing_fields:
                        error = f"Missing required parameters: {', '.join(missing_fields)}. You must provide these parameters."
                    else:
                        error += " — You must provide all required parameters. Do not call this tool with an empty body."
                return f"Tool error: {error}"

    return f"Unknown tool: {tool_name}"


async def execute_tool_call_with_events(
    tool_call: dict,
    tools: List[Any],
    conversation_id: str
) -> AsyncGenerator[Dict[str, Any], None]:
    """
    Execute a tool call and yield structured events.

    Yields events for tool_start, tool_end, and the final result marker.
    """
    tool_name = tool_call.get("name")
    tool_args = tool_call.get("args", {})

    # Emit tool_start event
    yield create_event(EventType.TOOL_START, conversation_id, tool_name=tool_name)

    # Find and execute the tool
    result = None
    error = None
    for tool in tools:
        if tool.name == tool_name:
            try:
                result = await tool.ainvoke(tool_args)
            except Exception as e:
                error = str(e)
                if "field required" in error.lower() or "validation error" in error.lower():
                    missing_fields = _extract_missing_fields(error)
                    if missing_fields:
                        error = f"Missing required parameters: {', '.join(missing_fields)}. You must provide these parameters."
                    else:
                        error += " — You must provide all required parameters. Do not call this tool with an empty body."
                result = f"Tool error: {error}"
            break
    else:
        error = f"Unknown tool: {tool_name}"
        result = error

    # Emit tool_end event
    yield create_event(EventType.TOOL_END, conversation_id, tool_name=tool_name, result=str(result)[:500])

    # Store the result for return (will be captured by caller)
    # We use a special marker to indicate the final result
    yield {"_result": result}
