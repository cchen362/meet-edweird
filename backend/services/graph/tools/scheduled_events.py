from typing import Optional

from services.graph.tool_decorator import tool
from services.graph.tools.context import get_current_conversation_id


@tool
async def schedule_event(
    description: str,
    scheduled_at: str,
    recurrence_pattern: Optional[str] = None,
    delivery_channel: Optional[str] = None,
) -> str:
    """
    Schedule a future event, reminder, or action.

    Call this before responding whenever you make a commitment to follow up, check back,
    or remind the user of something — the scheduled event IS part of the response, not an
    optional add-on. Use this when the user asks you to:
    - Set a reminder for a specific time
    - Schedule a message to be sent later
    - Create a recurring task or check-in
    - Do something at a future date/time

    The event will fire automatically at the scheduled time. Edward will
    receive the event description and execute the described action.

    Args:
        description: What Edward should do when the event fires. Be specific
            and include concrete details like contact names/numbers.
            (e.g. "Send Ben at +15551234567 a text reminding him about his dentist appointment"
            or "Tell the user it's time to take a break").
        scheduled_at: ISO 8601 datetime in the USER'S LOCAL TIME
            (e.g. "2025-01-15T14:30:00"). Do NOT convert to UTC — the system
            handles that automatically. Just use the same timezone as the
            current date/time shown in your context.
        recurrence_pattern: Optional cron pattern for recurring events
            (e.g. "0 9 * * *" for daily at 9 AM, "*/5 * * * *" for every 5 min).
            Cron times are also in the user's local timezone.
            Leave empty for one-time events.
        delivery_channel: Optional preferred channel: "whatsapp", "push", "chat", or null.
            Use "whatsapp" or "push" if the action involves sending a message.
            Use "chat" for in-app only (no external message). Defaults to null
            (auto-infer from description).

    Returns:
        Confirmation with event details
    """
    from services.scheduled_events_service import create_event
    from datetime import datetime, timezone

    conversation_id = get_current_conversation_id()

    try:
        # Parse the datetime
        dt = datetime.fromisoformat(scheduled_at)
        if dt.tzinfo is None:
            # Treat as local time — attach local timezone then convert to UTC
            local_dt = dt.astimezone()  # interprets naive as local
            dt = local_dt.astimezone(timezone.utc)
    except ValueError:
        return f"Invalid datetime format: {scheduled_at}. Use ISO 8601 format (e.g. 2025-01-15T14:30:00)."

    try:
        event = await create_event(
            description=description,
            scheduled_at=dt,
            recurrence_pattern=recurrence_pattern,
            conversation_id=conversation_id,
            delivery_channel=delivery_channel,
            created_by="edward",
        )
    except ValueError as e:
        return f"Error: {str(e)}"

    recurrence_info = f" (recurring: {recurrence_pattern})" if recurrence_pattern else " (one-time)"
    from services.scheduled_events_service import _format_local
    fire_time = _format_local(event.next_fire_at) if event.next_fire_at else scheduled_at
    return f"Event scheduled{recurrence_info}. Next fire: {fire_time}. ID: {event.id}"


@tool
async def list_scheduled_events(status: Optional[str] = None) -> str:
    """
    List scheduled events.

    Use this when the user asks about their reminders, scheduled events,
    or upcoming tasks.

    Args:
        status: Optional filter: "pending", "completed", "cancelled", "failed".
            Defaults to showing pending events.

    Returns:
        Formatted list of events
    """
    from services.scheduled_events_service import list_events

    events = await list_events(
        status=status,  # None = show all statuses (user can filter explicitly)
        conversation_id=None,  # Show events from ALL conversations
        limit=20,
    )

    if not events:
        filter_desc = f" with status '{status}'" if status else ""
        return f"No scheduled events found{filter_desc}."

    lines = [f"Found {len(events)} event(s):\n"]
    for e in events:
        from services.scheduled_events_service import _format_local
        fire_time = _format_local(e.next_fire_at, '%b %d, %Y %I:%M %p') if e.next_fire_at else "N/A"
        recurrence = f" [recurring: {e.recurrence_pattern}]" if e.recurrence_pattern else ""
        lines.append(f"- [{e.status}] {e.description} — fires: {fire_time}{recurrence} (ID: {e.id})")

    return "\n".join(lines)


@tool
async def cancel_scheduled_event(event_id: str) -> str:
    """
    Cancel a scheduled event.

    Use this when the user wants to cancel a reminder or scheduled action.

    Args:
        event_id: The ID of the event to cancel

    Returns:
        Confirmation message
    """
    from services.scheduled_events_service import cancel_event

    success = await cancel_event(event_id)
    if success:
        return f"Event {event_id} cancelled."
    return f"Could not cancel event {event_id}. It may already be completed or cancelled."


# List of all scheduled event tools
SCHEDULED_EVENT_TOOLS = [schedule_event, list_scheduled_events, cancel_scheduled_event]

SCHEDULED_EVENT_TOOL_NAMES = {"schedule_event", "list_scheduled_events", "cancel_scheduled_event"}


def get_scheduled_event_tools_description() -> str:
    """Get a description of available scheduled event tools for the system prompt."""
    return """
## Scheduled Events

Schedule future actions, reminders, and recurring tasks that fire automatically.

- **schedule_event**: Set a future action. Use user's LOCAL time (not UTC). Cron syntax for recurring.
- **list_scheduled_events / cancel_scheduled_event**: Manage existing events.

**CRITICAL**: Events run in an EPHEMERAL conversation with NO memory of the original context. The description must contain EVERYTHING needed: exact message text, database names, table and column names, phone numbers, calculations.

Bad: "Check on the dog's meds and track the response."
Good: "Send push notification 'Did you give the morning meds?' If YES, log to pet_tracker DB, medication_log table: INSERT INTO medication_log (date, given) VALUES (CURRENT_DATE, true)."

Events do NOT appear in the original chat. Use local time, standard cron syntax for recurring.
"""
