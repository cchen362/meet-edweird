"""
ToolRegistry: Unified tool management for Edward.

Collects tools from multiple sources (memory, documents, scheduled events,
push, heartbeat, search, WhatsApp, custom MCP) and filters based on skill
enabled state from the database.
"""

from typing import List, Any, Dict


# Track initialized state
_initialized = False


async def initialize_registry() -> None:
    """
    Initialize the tool registry.

    Called at startup to ensure the registry is ready before handling requests.
    """
    global _initialized

    # Force a cache refresh on startup
    await _get_skill_states(force_refresh=True)
    _initialized = True
    print("Tool registry initialized")


async def refresh_registry() -> None:
    """
    Refresh the tool registry after skill changes.

    Called when skills are enabled/disabled or reloaded.
    """
    await _get_skill_states(force_refresh=True)
    print("Tool registry refreshed")


# Simple skill state cache with short TTL
_skill_cache: Dict[str, bool] = {}
_cache_timestamp: float = 0
_CACHE_TTL_SECONDS = 5  # Short TTL to keep responsive while avoiding DB spam


async def _get_skill_states(force_refresh: bool = False) -> Dict[str, bool]:
    """
    Get enabled state for all skills.

    Uses a short-lived cache to avoid DB queries on every request.
    """
    global _skill_cache, _cache_timestamp

    import time
    now = time.time()

    if not force_refresh and _skill_cache and (now - _cache_timestamp) < _CACHE_TTL_SECONDS:
        return _skill_cache

    from services.skills_service import is_skill_enabled

    _skill_cache = {
        "whatsapp_mcp": await is_skill_enabled("whatsapp_mcp"),
        "brave_search": await is_skill_enabled("brave_search"),
        "push_notifications": await is_skill_enabled("push_notifications"),
    }
    _cache_timestamp = now

    return _skill_cache


def _get_memory_tools() -> List[Any]:
    """Get memory tools (always available)."""
    from services.graph.tools.memory import MEMORY_TOOLS
    return MEMORY_TOOLS


def _get_document_tools() -> List[Any]:
    """Get document tools (always available)."""
    from services.graph.tools.documents import DOCUMENT_TOOLS
    return DOCUMENT_TOOLS


def _get_scheduled_event_tools() -> List[Any]:
    """Get scheduled event tools (always available)."""
    from services.graph.tools.scheduled_events import SCHEDULED_EVENT_TOOLS
    return SCHEDULED_EVENT_TOOLS


def _get_heartbeat_tools() -> List[Any]:
    """Get heartbeat tools (always available)."""
    from services.graph.tools.heartbeat import HEARTBEAT_TOOLS
    return HEARTBEAT_TOOLS


async def _get_push_notification_tools(skill_states: Dict[str, bool]) -> List[Any]:
    """Get push notification tools (available when skill enabled and configured)."""
    if not skill_states.get("push_notifications"):
        return []

    from services.push_service import is_configured
    if not is_configured():
        return []

    from services.graph.tools.push import PUSH_NOTIFICATION_TOOLS
    return PUSH_NOTIFICATION_TOOLS


def _get_whatsapp_mcp_tools(skill_states: Dict[str, bool]) -> List[Any]:
    """
    Get WhatsApp bridge tools if whatsapp_mcp is enabled.

    Uses the custom Baileys bridge REST API instead of MCP tools.
    """
    if not skill_states.get("whatsapp_mcp"):
        return []

    from services.whatsapp_bridge_client import is_available

    if not is_available():
        return []

    from services.whatsapp_bridge_tools import WHATSAPP_BRIDGE_TOOLS
    return WHATSAPP_BRIDGE_TOOLS


def _get_search_tools(skill_states: Dict[str, bool]) -> List[Any]:
    """
    Get search tools if brave_search is enabled.

    Args:
        skill_states: Dict of skill_id -> enabled

    Returns:
        List of search tools
    """
    if not skill_states.get("brave_search"):
        return []

    from services.graph.tools.search import web_search, fetch_page_content

    return [web_search, fetch_page_content]


def _get_custom_mcp_tools() -> List[Any]:
    """Get tools from all running custom MCP servers."""
    try:
        from services.custom_mcp_service import get_all_custom_tools
        return get_all_custom_tools()
    except Exception:
        return []


def _get_custom_mcp_self_service_tools() -> List[Any]:
    """Get the LLM tools for managing custom MCP servers (always available)."""
    from services.custom_mcp_tools import CUSTOM_MCP_TOOLS
    return CUSTOM_MCP_TOOLS


# D-001-4: Edward does not spawn workers, self-code, or execute code. The orchestrator,
# evolution, Claude Code session, code-sandbox, and task-plan tools were deleted in
# Plan 001 M3 after the 2026-09-09 usage review (21 of 26 orchestrator tasks failed,
# no companion use). Do not re-add a worker, self-edit, or code-execution tool here
# without a concrete usage case from the owner (see docs/DECISIONS.md, D-001-4).
async def get_available_tools() -> List[Any]:
    """
    Get all tools that are currently available based on skill state.

    Returns:
        List of tools filtered by enabled skills.
        Memory tools are always included.
    """
    skill_states = await _get_skill_states()

    tools = []
    seen_names = set()

    def add_tools(new_tools: List[Any]) -> None:
        """Add tools, deduplicating by tool name."""
        for tool in new_tools:
            if tool.name not in seen_names:
                tools.append(tool)
                seen_names.add(tool.name)

    # Memory tools are always available
    add_tools(_get_memory_tools())

    # Document tools are always available
    add_tools(_get_document_tools())

    # Scheduled event tools are always available
    add_tools(_get_scheduled_event_tools())

    # Heartbeat tools are always available
    add_tools(_get_heartbeat_tools())

    # Push notification tools (available when skill enabled and VAPID keys configured)
    add_tools(await _get_push_notification_tools(skill_states))

    # Add WhatsApp MCP tools if enabled
    add_tools(_get_whatsapp_mcp_tools(skill_states))

    # Add search tools if enabled
    add_tools(_get_search_tools(skill_states))

    # Custom MCP self-service tools (always available)
    add_tools(_get_custom_mcp_self_service_tools())

    # Tools from custom MCP servers Edward has added
    add_tools(_get_custom_mcp_tools())

    return tools


def get_tool_descriptions(tools: List[Any]) -> str:
    """
    Generate system prompt section describing available tools.

    Args:
        tools: List of available tools

    Returns:
        Formatted string for system prompt
    """
    from services.graph.tools.memory import get_memory_tools_description
    from services.graph.tools.documents import get_document_tools_description
    from services.graph.tools.scheduled_events import get_scheduled_event_tools_description
    from services.graph.tools.search import get_search_tools_description
    from services.graph.tools.push import get_push_notification_tools_description
    from services.graph.tools.heartbeat import get_heartbeat_tools_description

    # Get tool names for filtering
    tool_names = {t.name for t in tools}

    sections = []

    # Memory tools section (always included since memory tools always available)
    if any(name in tool_names for name in ["remember_update", "remember_forget", "remember_search"]):
        sections.append(get_memory_tools_description())

    # Document tools section (always included)
    if any(name in tool_names for name in ["save_document", "read_document", "edit_document", "search_documents", "list_documents", "delete_document"]):
        sections.append(get_document_tools_description())

    # Scheduled event tools section (always included)
    if any(name in tool_names for name in ["schedule_event", "list_scheduled_events", "cancel_scheduled_event"]):
        sections.append(get_scheduled_event_tools_description())

    # Heartbeat tools section (always included)
    if "review_heartbeat" in tool_names:
        sections.append(get_heartbeat_tools_description())

    # Search tools section
    if any(name in tool_names for name in ["web_search", "fetch_page_content"]):
        sections.append(get_search_tools_description())

    # Push notification tools section
    if "send_push_notification" in tool_names:
        sections.append(get_push_notification_tools_description())

    # GitHub MCP tools section (guardrail for write actions)
    # Sentinel: github-mcp-server always exposes "get_me" (prefixed as "github_get_me" by custom MCP)
    if "get_me" in tool_names or "github_get_me" in tool_names:
        sections.append(_get_github_mcp_description())

    # Custom MCP self-service tools section
    if any(name in tool_names for name in ["search_mcp_servers", "add_mcp_server", "list_custom_servers", "remove_mcp_server", "update_mcp_server", "restart_mcp_server"]):
        sections.append(_get_custom_mcp_description())

    # MCP tools use their own descriptions from the MCP server

    return "\n".join(sections)


def _get_github_mcp_description() -> str:
    """Write-confirmation guardrail for GitHub MCP tools."""
    return """## GitHub (Read + Soft Write)

You have access to GitHub tools for reading repositories, files, issues, and pull
requests, and for creating issues and comments.

IMPORTANT — Confirmation required before any write action:
Before calling any tool that creates, modifies, or closes a GitHub resource
(creating an issue, posting a comment, opening or updating a PR, etc.), you MUST
first describe exactly what you are about to do — including repo, resource type,
and content — and wait for the user to explicitly confirm before calling the tool.
Example: "I'm about to open an issue titled 'X' in org/repo. Shall I proceed?"

Read-only tools (list_*, get_*, search_*) do not require confirmation."""


def _get_custom_mcp_description() -> str:
    """Get description for custom MCP self-service tools."""
    return """## Custom MCP Servers (Self-Service)

You can discover and install MCP servers to extend your own capabilities at runtime.
No restart required — new tools become available immediately.

- `search_mcp_servers` — Search GitHub for MCP server packages
- `add_mcp_server` — Install and start a new MCP server (npx or uvx)
- `list_custom_servers` — List servers you've added with their status and config
- `update_mcp_server` — Update a server's env vars, args, or description (auto-restarts if running)
- `restart_mcp_server` — Restart a server (useful for error recovery)
- `remove_mcp_server` — Stop and remove a server

Use "npx" runtime for Node.js/TypeScript packages, "uvx" for Python packages, and "binary" for pre-installed native binaries already on PATH (package_name becomes the command directly, no package manager involved).
Environment variables can be passed as a JSON object to configure servers that need API keys.
To update env vars on an existing server, use update_mcp_server — env vars merge by default (set a key to "" to remove it)."""
