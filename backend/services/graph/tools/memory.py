from typing import Optional

from services.graph.tool_decorator import tool


@tool
async def remember_update(memory_id: str, new_content: str) -> str:
    """
    Update an existing memory with new or corrected information.

    Use this when the user corrects something you previously remembered, when a fact has
    changed (new phone number, updated preference, changed circumstance), or when a memory
    is outdated or incomplete. The memory's embedding will be regenerated so future retrieval
    reflects the new content. For entirely new information with no existing memory to update,
    use remember_save instead.

    Args:
        memory_id: The ID of the memory to update (from the memory context)
        new_content: The new content for this memory

    Returns:
        Confirmation message
    """
    from services.memory_service import update_memory, get_memory_by_id

    # Verify memory exists
    existing = await get_memory_by_id(memory_id)
    if not existing:
        return f"Memory with ID {memory_id} not found. Cannot update."

    updated = await update_memory(memory_id=memory_id, content=new_content)
    if updated:
        return "ok"
    return "Failed to update memory."


@tool
async def remember_forget(memory_id: str) -> str:
    """
    Delete/forget a specific memory.

    Use this when the user explicitly asks to forget something, or when
    information is no longer accurate or relevant.

    Args:
        memory_id: The ID of the memory to delete (from the memory context)

    Returns:
        Confirmation message
    """
    from services.memory_service import delete_memory, get_memory_by_id

    # Get memory content for confirmation
    existing = await get_memory_by_id(memory_id)
    if not existing:
        return f"Memory with ID {memory_id} not found. Nothing to delete."

    deleted = await delete_memory(memory_id)
    if deleted:
        return "ok"
    return "Failed to delete memory."


@tool
async def remember_search(query: str, memory_type: Optional[str] = None) -> str:
    """
    Search through memories for specific information.

    Use this to find memories related to a topic, or to check what
    information is stored about something specific.

    Args:
        query: Search query describing what to find
        memory_type: Optional filter: 'fact', 'preference', 'context', or 'instruction'

    Returns:
        List of matching memories with their IDs
    """
    from services.memory_service import search_memories

    memories, total = await search_memories(
        query=query,
        memory_type=memory_type,
        limit=10
    )

    if not memories:
        return f"No memories found matching '{query}'."

    results = [f"Found {total} memories matching '{query}':\n"]
    for m in memories[:10]:
        score_str = f" (score: {m.score:.2f})" if m.score > 0 else ""
        tn = getattr(m, 'temporal_nature', 'timeless') or 'timeless'
        tn_tag = f" [{tn}]" if tn != "timeless" else ""
        results.append(f"- [{m.memory_type}] {m.content}{tn_tag} (ID: {m.id}){score_str}")

    return "\n".join(results)


# List of all memory tools for binding to LLM
MEMORY_TOOLS = [remember_update, remember_forget, remember_search]


def get_memory_tools_description() -> str:
    """Get a description of available memory tools for the system prompt."""
    return """
## Memory Management

Tools for managing your long-term memory: **remember_update**, **remember_forget**, **remember_search**.

When relevant memories appear in your context, use their IDs to update or delete them.

Memories are short snippets. For full text, use documents.
"""
