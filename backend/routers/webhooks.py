"""
Webhook handlers for external services.

Currently supports:
- WhatsApp Bridge @mention webhooks
"""

import asyncio
import json
from fastapi import APIRouter, HTTPException, Request

router = APIRouter()


# ─── WhatsApp Bridge Webhook ─────────────────────────────────────────────────

@router.post("/webhook/whatsapp")
async def whatsapp_bridge_webhook(request: Request):
    """
    Handle incoming @edward mention notifications from the WhatsApp bridge.

    The Baileys bridge detects @edward in real-time and POSTs here.
    We create a HeartbeatEventModel and trigger immediate triage.
    """
    from services.database import async_session, HeartbeatEventModel
    from sqlalchemy import select

    try:
        data = await request.json()
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid JSON body")

    chat_id = data.get("chat_id", "")
    chat_name = data.get("chat_name", chat_id)
    sender = data.get("sender", "")
    sender_name = data.get("sender_name", "")
    text = data.get("text", "")
    message_id = data.get("message_id", "")
    is_from_me = data.get("is_from_me", False)

    if not chat_id or not text:
        raise HTTPException(status_code=400, detail="chat_id and text required")

    # Safety net: resolve @lid JIDs if bridge didn't already
    if chat_id.endswith("@lid"):
        try:
            from services.whatsapp_bridge_client import resolve_lid, is_available
            if is_available():
                resolved = await resolve_lid(chat_id)
                if resolved != chat_id:
                    print(f"[Webhook] Resolved LID {chat_id} → {resolved}")
                    chat_id = resolved
        except Exception as e:
            print(f"[Webhook] LID resolution failed: {e}")

    source_id = f"whatsapp:{message_id}" if message_id else f"whatsapp:{chat_id}_{hash(text)}"

    # Dedup and store
    async with async_session() as session:
        existing = await session.execute(
            select(HeartbeatEventModel.id).where(
                HeartbeatEventModel.source_id == source_id
            )
        )
        if existing.scalar_one_or_none():
            return {"status": "duplicate"}

        event = HeartbeatEventModel(
            source="whatsapp",
            event_type="message_received",
            sender=sender,
            contact_name=sender_name or chat_name,
            chat_identifier=chat_id,
            chat_name=chat_name,
            summary=text[:200],
            raw_data=json.dumps(data),
            source_id=source_id,
            is_from_user=bool(is_from_me),
        )
        session.add(event)
        await session.commit()

    print(f"[Webhook] WhatsApp @mention from {sender_name or sender} in {chat_name}: {text[:80]}")

    # Trigger triage in background
    async def _trigger():
        try:
            from services.heartbeat.heartbeat_service import trigger_immediate_triage
            await trigger_immediate_triage()
        except Exception as e:
            print(f"[Webhook] WhatsApp triage trigger error: {e}")

    asyncio.create_task(_trigger())

    return {"status": "accepted"}
