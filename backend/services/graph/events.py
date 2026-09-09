"""SSE event contract with the frontend.

`EventType` names are the contract with `frontend/lib/api.ts` — do not rename
a value without updating the frontend's event handling to match.
"""

from typing import Any, Dict


# Event types for structured SSE streaming
class EventType:
    THINKING = "thinking"
    PROGRESS = "progress"
    TOOL_START = "tool_start"
    TOOL_END = "tool_end"
    CONTENT = "content"
    ERROR = "error"
    DONE = "done"
    INTERRUPTED = "interrupted"


def create_event(event_type: str, conversation_id: str, **kwargs) -> Dict[str, Any]:
    """Create a structured event for SSE streaming."""
    return {
        "type": event_type,
        "conversation_id": conversation_id,
        **kwargs
    }


# Human-readable labels for tool progress events
TOOL_LABELS: Dict[str, str] = {
    # Memory
    "remember_search": "Searching memories",
    "remember_update": "Saving memory",
    "remember_forget": "Forgetting memory",
    # Web
    "web_search": "Searching the web",
    "fetch_page_content": "Reading page",
    # Documents
    "save_document": "Saving document",
    "read_document": "Reading document",
    "edit_document": "Editing document",
    "search_documents": "Searching documents",
    "list_documents": "Listing documents",
    "delete_document": "Deleting document",
    # Scheduled events
    "schedule_event": "Scheduling event",
    "list_scheduled_events": "Checking schedule",
    "cancel_scheduled_event": "Cancelling event",
    # Push
    "send_push_notification": "Sending notification",
    # Custom MCP
    "search_mcp_servers": "Searching MCP servers",
    "add_mcp_server": "Adding MCP server",
    "list_custom_servers": "Listing MCP servers",
    "remove_mcp_server": "Removing MCP server",
    "update_mcp_server": "Updating MCP server",
    "restart_mcp_server": "Restarting MCP server",
    # Heartbeat
    "review_heartbeat": "Reviewing heartbeat",
}


def tool_label(tool_name: str) -> str:
    """Return a human-readable label for a tool name."""
    if tool_name in TOOL_LABELS:
        return TOOL_LABELS[tool_name]
    # MCP tool prefix (e.g. "whatsapp_send_message" → "Whatsapp: Send Message")
    if "_" in tool_name:
        parts = tool_name.split("_", 1)
        return f"{parts[0].title()}: {parts[1].replace('_', ' ').title()}"
    return tool_name.replace("_", " ").title()
