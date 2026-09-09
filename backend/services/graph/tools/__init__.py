"""LLM tool definitions, split by domain (memory, documents, scheduled_events,
heartbeat, push, search, context).

`services/tool_registry.py` is the single aggregator that binds these tools
per request according to skill enabled-state — import from the concrete
submodule you need rather than expecting re-exports here.

WhatsApp tools live in `services/whatsapp_bridge_tools.py` and custom-MCP
tools in `services/custom_mcp_tools.py` — not in this package.
"""
