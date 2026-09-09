from typing import Optional

from services.graph.tool_decorator import tool


@tool
async def review_heartbeat(
    sender: Optional[str] = None,
    status_filter: Optional[str] = None,
    limit: int = 15,
) -> str:
    """
    Review recent messages and events you've noticed via your heartbeat system.

    Use this when the user asks what you've noticed, what messages came in,
    or wants to know about recent activity from contacts.

    Args:
        sender: Optional — filter by sender phone/email (partial match)
        status_filter: Optional — "pending", "dismissed", "noted", "acted", "escalated"
        limit: Max events to return (default 15)

    Returns:
        Formatted list of recent heartbeat events
    """
    from services.database import HeartbeatEventModel, async_session
    from sqlalchemy import select, desc

    async with async_session() as session:
        query = select(HeartbeatEventModel).order_by(desc(HeartbeatEventModel.created_at)).limit(limit)

        if sender:
            query = query.where(HeartbeatEventModel.sender.ilike(f"%{sender}%"))
        if status_filter:
            query = query.where(HeartbeatEventModel.triage_status == status_filter)

        result = await session.execute(query)
        events = result.scalars().all()

    if not events:
        filter_desc = ""
        if sender:
            filter_desc += f" from '{sender}'"
        if status_filter:
            filter_desc += f" with status '{status_filter}'"
        return f"No heartbeat events found{filter_desc}."

    lines = [f"Found {len(events)} recent event(s):\n"]
    for e in events:
        time_str = e.created_at.strftime("%b %d, %I:%M %p") if e.created_at else "unknown"
        direction = "outgoing" if e.is_from_user else "incoming"
        sender_str = e.sender or "unknown"
        summary_str = e.summary or "(no summary)"
        chat_str = f" in {e.chat_name}" if e.chat_name else ""
        lines.append(f"- [{e.triage_status}] {time_str} — {direction} from {sender_str}{chat_str}: {summary_str}")

    return "\n".join(lines)


HEARTBEAT_TOOLS = [review_heartbeat]

HEARTBEAT_TOOL_NAMES = {"review_heartbeat"}


def get_heartbeat_tools_description() -> str:
    """Get a description of available heartbeat tools for the system prompt."""
    return """
## Heartbeat (Background Awareness)

You have a heartbeat system that passively monitors incoming and outgoing WhatsApp messages.
Messages are triaged automatically (dismiss/note/act/escalate).

1. **review_heartbeat(sender?, status_filter?, limit?)**: Review recent messages you've noticed.
   - Filter by sender (partial match on phone/email)
   - Filter by triage status: "pending", "dismissed", "noted", "acted", "escalated"
   - Use this when the user asks what you've noticed or about recent messages from someone
"""
