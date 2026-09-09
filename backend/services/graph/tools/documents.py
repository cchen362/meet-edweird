from typing import Optional

from services.graph.tool_decorator import tool
from services.graph.tools.context import get_current_conversation_id


@tool
async def save_document(title: str, content: str, tags: Optional[str] = None) -> str:
    """
    Save a document to the persistent store for long-term reference.

    Use this proactively — not only when the user explicitly asks. If a conversation
    produces something durable (a plan, a list, a recipe, research notes, a decision log,
    instructions), save it. The right signal: "would this be useful to retrieve in a future
    conversation?" Documents support full-text search. Use for structured or lengthy
    content; use remember_save for short facts and preferences.

    Args:
        title: A descriptive title for the document
        content: The full document content (markdown supported)
        tags: Optional comma-separated tags for categorization (e.g. "recipe,cooking,italian")

    Returns:
        Confirmation with the document ID
    """
    from services.document_service import save_document as _save, Document

    conversation_id = get_current_conversation_id()

    doc = Document(
        id=None,
        title=title,
        content=content,
        tags=tags,
        source_conversation_id=conversation_id,
    )

    saved = await _save(doc)
    tag_info = f" (tags: {tags})" if tags else ""
    return f"Document saved: \"{saved.title}\"{tag_info} (ID: {saved.id})"


@tool
async def read_document(document_id: str) -> str:
    """
    Read the full content of a document from the store.

    Use this when you see a relevant document title in your context and need
    to read the full content. Also use when the user asks to see a stored document.

    Args:
        document_id: The document ID

    Returns:
        Full document content with title and tags
    """
    from services.document_service import get_document_by_id

    doc = await get_document_by_id(document_id)
    if not doc:
        return f"Document {document_id} not found."

    parts = [f"# {doc.title}"]
    if doc.tags:
        parts.append(f"Tags: {doc.tags}")
    parts.append("")
    parts.append(doc.content)
    return "\n".join(parts)


@tool
async def edit_document(
    document_id: str,
    title: Optional[str] = None,
    content: Optional[str] = None,
    tags: Optional[str] = None,
) -> str:
    """
    Edit an existing document. Only provide fields you want to change.

    Use this when the user wants to update a stored document's content, title, or tags.

    Args:
        document_id: The document ID to edit
        title: New title (optional)
        content: New content (optional)
        tags: New tags, comma-separated (optional)

    Returns:
        Confirmation message
    """
    from services.document_service import update_document

    updated = await update_document(
        document_id=document_id,
        title=title,
        content=content,
        tags=tags,
    )

    if not updated:
        return f"Document {document_id} not found."

    return f"Document updated: \"{updated.title}\" (ID: {updated.id})"


@tool
async def search_documents(query: str, tags: Optional[str] = None) -> str:
    """
    Search for documents by semantic similarity and keywords.

    Use this when looking for stored documents on a topic, or when the user
    asks about documents they've saved.

    Args:
        query: Search query describing what to find
        tags: Optional comma-separated tags to filter by

    Returns:
        List of matching documents with titles and IDs
    """
    from services.document_service import search_documents as _search

    docs, total = await _search(query=query, tags=tags, limit=10)

    if not docs:
        return f"No documents found matching '{query}'."

    lines = [f"Found {total} document(s) matching '{query}':\n"]
    for d in docs:
        tag_info = f" [{d.tags}]" if d.tags else ""
        score_info = f" (score: {d.score:.2f})" if d.score > 0 else ""
        preview = d.content[:100].replace("\n", " ") + ("..." if len(d.content) > 100 else "")
        lines.append(f"- **{d.title}**{tag_info}{score_info} (ID: {d.id})")
        lines.append(f"  {preview}")

    return "\n".join(lines)


@tool
async def list_documents(tags: Optional[str] = None) -> str:
    """
    List all documents in the store.

    Use this when the user wants to see what documents are saved,
    or to browse by tag.

    Args:
        tags: Optional comma-separated tags to filter by

    Returns:
        List of all documents with titles, tags, and IDs
    """
    from services.document_service import list_documents as _list

    docs, total = await _list(limit=20, tags=tags)

    if not docs:
        filter_info = f" with tags '{tags}'" if tags else ""
        return f"No documents found{filter_info}."

    lines = [f"Found {total} document(s):\n"]
    for d in docs:
        tag_info = f" [{d.tags}]" if d.tags else ""
        date_info = d.updated_at.strftime("%b %d, %Y") if d.updated_at else "N/A"
        lines.append(f"- **{d.title}**{tag_info} — updated {date_info} (ID: {d.id})")

    return "\n".join(lines)


@tool
async def delete_document(document_id: str) -> str:
    """
    Delete a document from the store.

    Use this when the user explicitly asks to remove a stored document.

    Args:
        document_id: The document ID to delete

    Returns:
        Confirmation message
    """
    from services.document_service import delete_document as _delete

    deleted = await _delete(document_id)
    if deleted:
        return f"Document {document_id} deleted."
    return f"Document {document_id} not found."


# List of all document tools
DOCUMENT_TOOLS = [save_document, read_document, edit_document, search_documents, list_documents, delete_document]

DOCUMENT_TOOL_NAMES = {"save_document", "read_document", "edit_document", "search_documents", "list_documents", "delete_document"}


def get_document_tools_description() -> str:
    """Get a description of available document tools for the system prompt."""
    return """
## Document Store

Persistent storage for full documents -- recipes, notes, guides, reference material.

- **save_document / read_document / edit_document / search_documents / list_documents / delete_document**

When relevant documents appear in context (titles only), use read_document to fetch full content.

**Knowledge layers**: Memories = short facts (auto-extracted). Documents = full text (explicit save).
"""
