from typing import Optional

from services.graph.tool_decorator import tool
from services.graph.tools.context import get_current_conversation_id


@tool
async def send_push_notification(
    title: str,
    body: str,
    url: Optional[str] = None,
) -> str:
    """
    Send a push notification to the user's devices.

    Use this when you need to proactively alert the user about something
    important, even when they're not actively using the app. Push notifications
    appear on the user's phone or computer.

    Best used for:
    - Urgent alerts that need immediate attention
    - Reminders when the user might not be checking the app
    - Important status updates

    Args:
        title: Short notification title (keep under 50 chars)
        body: Notification body text (keep under 100 chars for best display)
        url: Optional URL to open when notification is clicked

    Returns:
        Confirmation with delivery status
    """
    from services.push_service import send_push_notification as send_push, is_configured
    from services.conversation_service import mark_user_notified

    if not is_configured():
        return "Push notifications not configured. VAPID keys are not set."

    # If no explicit URL provided, link to the current conversation
    conversation_id = get_current_conversation_id()
    if not url and conversation_id:
        url = f"/?c={conversation_id}"

    try:
        result = await send_push(
            title=title,
            body=body,
            url=url or "/",
            tag="edward-proactive",
        )

        if result.get("error"):
            return f"Push notification failed: {result['error']}"

        sent = result.get("sent", 0)
        failed = result.get("failed", 0)
        total = result.get("total", 0)

        if total == 0:
            return "No active push subscriptions. User has not enabled notifications."

        if sent > 0:
            # Mark this conversation as having notified the user (for filtering)
            if conversation_id:
                await mark_user_notified(conversation_id)
            return f"Push notification sent to {sent} device(s)."
        else:
            return f"Push notification failed to deliver to {failed} device(s)."

    except Exception as e:
        return f"Push notification error: {str(e)}"


# List of all push notification tools
PUSH_NOTIFICATION_TOOLS = [send_push_notification]


def get_push_notification_tools_description() -> str:
    """Get a description of available push notification tools for the system prompt."""
    return """
## Push Notifications

- **send_push_notification**: Send push notification to user's devices. Use sparingly -- only for important alerts that need immediate attention. Works even when user isn't in the app.
"""
