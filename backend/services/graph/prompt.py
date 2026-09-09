"""System prompt assembly: Edward's character plus memory/document context."""

from datetime import datetime
from typing import List, Any, Optional

from services.tool_registry import get_tool_descriptions

# Context budget constants
MAX_NORMAL_MEMORIES = 5
MAX_ENRICHED_MEMORIES = 5
MAX_DOCUMENTS = 3
MAX_MEMORY_CONTEXT_CHARS = 8000


EDWARD_CHARACTER = """
You are Edward — a personal AI assistant who is witty, a little cheeky, and genuinely warm. You have been built up over time through real conversations and have accumulated memories, documents, and knowledge that you actively draw on. You are not a generic chatbot.

Your default is to act, not to ask. When something should be done and the cost of being wrong is low, do it and report back. Think ahead — anticipate what the user will need next, not just what they asked for right now. When a commitment is made to follow up, call schedule_event() before responding — the reminder is part of the response, not an afterthought. When a topic has depth or recurrence, build something durable: a document or a memory.

Own your decisions. Act or decline — never hedge. Saying "If you want, I can..." or "Would you like me to..." means you chose not to act; say that plainly instead. Post-mortem notes ("I should have saved that") without action are not acceptable — if it should have been done, do it now.

When genuinely uncertain about intent, pick the most reasonable interpretation and act. State what you assumed and why. Adjust if corrected. Ask only when the action is hard to reverse or the stakes are high enough that guessing wrong would cost more than asking. When tool results include identifying fields (name, contact, sender), compare them to what was asked — if there's a mismatch, either make one cheap verification call or state the assumption explicitly.
"""


def _relative_time(dt: Optional[datetime]) -> str:
    """Format a datetime as a human-readable relative time string."""
    if not dt:
        return "unknown"
    now = datetime.now()
    delta = now - dt
    days = delta.days
    if days < 1:
        hours = delta.seconds // 3600
        if hours < 1:
            return "just now"
        return f"{hours}h ago"
    if days < 7:
        return f"{days}d ago"
    if days < 30:
        weeks = days // 7
        return f"{weeks}w ago"
    if days < 365:
        months = days // 30
        return f"{months}mo ago"
    years = days // 365
    return f"{years}y ago"


def _format_temporal_tag(memory) -> str:
    """Format the temporal metadata tag for a memory in the LLM context."""
    tn = getattr(memory, 'temporal_nature', 'timeless') or 'timeless'
    created = getattr(memory, 'created_at', None)
    last_acc = getattr(memory, 'last_accessed', None)
    acc_count = getattr(memory, 'access_count', 0) or 0

    age = _relative_time(created)

    if tn == "timeless":
        return f"[timeless, learned {age}]"
    else:
        parts = [tn, f"learned {age}"]
        if last_acc:
            parts.append(f"last checked {_relative_time(last_acc)}")
        if acc_count > 1:
            parts.append(f"accessed {acc_count}x")
        return f"[{', '.join(parts)}]"


def build_memory_context(
    memories: list,
    tools: List[Any] = None,
    documents: list = None,
    enriched_memories: list = None,
) -> str:
    """Build the memory context section for the system prompt.

    Applies MAX_MEMORY_CONTEXT_CHARS budget. If over budget, enrichments
    are truncated first.
    """
    memory_parts = []

    if memories:
        memory_parts.append("\n\n## Relevant Context from Previous Conversations:")
        for memory in memories[:MAX_NORMAL_MEMORIES]:
            temporal_tag = _format_temporal_tag(memory)
            tier = getattr(memory, 'tier', 'observation') or 'observation'
            tier_tag = f" [{tier}]" if tier != "observation" else ""
            memory_parts.append(
                f"- [{memory.memory_type}]{tier_tag} {memory.content} {temporal_tag} (memory_id: {memory.id})"
            )

    enrichment_parts = []
    if enriched_memories:
        enrichment_parts.append("\n\n## Additional Context from Reflection:")
        for memory in enriched_memories[:MAX_ENRICHED_MEMORIES]:
            temporal_tag = _format_temporal_tag(memory)
            tier = getattr(memory, 'tier', 'observation') or 'observation'
            tier_tag = f" [{tier}]" if tier != "observation" else ""
            enrichment_parts.append(
                f"- [{memory.memory_type}]{tier_tag} {memory.content} {temporal_tag} (memory_id: {memory.id})"
            )

    # Apply context budget — truncate enrichments first if over
    memory_text = "\n".join(memory_parts)
    enrichment_text = "\n".join(enrichment_parts)
    total_len = len(memory_text) + len(enrichment_text)

    if total_len > MAX_MEMORY_CONTEXT_CHARS:
        # Trim enrichments to fit
        remaining = MAX_MEMORY_CONTEXT_CHARS - len(memory_text)
        if remaining > 0:
            enrichment_text = enrichment_text[:remaining]
        else:
            enrichment_text = ""

    context_parts = []
    if memory_text:
        context_parts.append(memory_text)
    if enrichment_text:
        context_parts.append(enrichment_text)

    if documents:
        context_parts.append("\n\n## Relevant Documents in Store:")
        for doc in documents[:MAX_DOCUMENTS]:
            tag_info = f" [{doc.tags}]" if doc.tags else ""
            context_parts.append(
                f"- {doc.title}{tag_info} (document_id: {doc.id})"
            )
        context_parts.append(
            "Use read_document(document_id) to fetch full content when needed."
        )

    if tools:
        context_parts.append(get_tool_descriptions(tools))

    return "\n".join(context_parts)
