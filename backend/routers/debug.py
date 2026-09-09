"""
Debug router for Edward development and observability.

Provides endpoints for:
- Memory statistics and listing
- Session state inspection
"""

from fastapi import APIRouter, HTTPException
from typing import Optional

from services.memory_service import get_memory_stats, get_all_memories

router = APIRouter()


@router.get("/debug/memories")
async def get_memories(limit: int = 50, offset: int = 0):
    """
    Get stored memories with pagination.

    Args:
        limit: Maximum number of memories to return (default 50)
        offset: Number of memories to skip (default 0)

    Returns:
        List of memories and pagination info
    """
    try:
        memories = await get_all_memories(limit=limit, offset=offset)
        stats = await get_memory_stats()

        return {
            "memories": [
                {
                    "id": m.id,
                    "content": m.content,
                    "memory_type": m.memory_type,
                    "importance": m.importance,
                    "source_conversation_id": m.source_conversation_id,
                    "created_at": (m.created_at.isoformat() + "Z") if m.created_at else None,
                    "updated_at": (m.updated_at.isoformat() + "Z") if m.updated_at else None,
                    "last_accessed": (m.last_accessed.isoformat() + "Z") if m.last_accessed else None,
                    "access_count": m.access_count,
                    "user_id": m.user_id
                }
                for m in memories
            ],
            "stats": stats,
            "pagination": {
                "limit": limit,
                "offset": offset,
                "total": stats["total"]
            }
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/debug/memories/stats")
async def get_memories_stats():
    """
    Get statistics about stored memories.

    Returns:
        - Total count
        - Count by type (fact, preference, context, instruction)
        - Average importance
    """
    try:
        stats = await get_memory_stats()
        return stats
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/debug/health")
async def debug_health():
    """
    Extended health check for debugging.

    Returns status of various components.
    """
    from services.database import async_session

    status = {
        "checkpoint_store": "unknown",
        "database": "unknown",
        "memory_service": "unknown"
    }

    # Check checkpoint store
    try:
        from services.checkpoint_store import get_messages
        # Quick smoke test — get_messages on a non-existent ID should return []
        test = await get_messages("__health_check__")
        status["checkpoint_store"] = "healthy"
    except Exception as e:
        status["checkpoint_store"] = f"error: {str(e)}"

    # Check database
    try:
        async with async_session() as session:
            await session.execute("SELECT 1")
            status["database"] = "healthy"
    except Exception as e:
        status["database"] = f"error: {str(e)}"

    # Check memory service
    try:
        stats = await get_memory_stats()
        status["memory_service"] = "healthy"
        status["memory_count"] = stats["total"]
    except Exception as e:
        status["memory_service"] = f"error: {str(e)}"

    return status
