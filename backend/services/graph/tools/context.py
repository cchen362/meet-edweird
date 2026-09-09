from typing import Optional

# Context variable for the current conversation_id — safe for concurrent turns.
# Relied on by document tools, scheduled-event tools, push tools, heartbeat
# tools, the scheduler service, and the WhatsApp triage service to find the
# conversation a tool call belongs to.
import contextvars
_current_conversation_id: contextvars.ContextVar[Optional[str]] = contextvars.ContextVar(
    '_current_conversation_id', default=None
)


def set_current_conversation_id(conversation_id: str) -> None:
    """Set the current conversation ID so tools can find the current conversation."""
    _current_conversation_id.set(conversation_id)


def get_current_conversation_id() -> Optional[str]:
    """Get the current conversation ID for tool context."""
    return _current_conversation_id.get()
