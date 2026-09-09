"""
Tool schema conversion for the OpenAI Responses API.

Converts EdwardTool and MCPToolWrapper objects into the tool schema format
expected by openai.responses.create(tools=[...]) — the only LLM tool-calling
surface Edward calls (chat is GPT via Codex OAuth; Tier 2 Haiku calls make no
tool calls). There is no Anthropic tool schema path.
"""

from typing import Any


def tool_to_openai_schema(tool: Any) -> dict:
    """Convert a tool object to OpenAI Responses API function tool format.

    Works with both EdwardTool and MCPToolWrapper (same as Anthropic converter).
    """
    schema = _extract_json_schema(tool)

    clean_schema = {
        "type": schema.get("type", "object"),
        "properties": schema.get("properties", {}),
    }
    if "required" in schema:
        clean_schema["required"] = schema["required"]

    return {
        "type": "function",
        "name": tool.name,
        "description": tool.description or "",
        "parameters": clean_schema,
    }


def tools_to_openai_schemas(tools: list) -> list[dict]:
    """Convert a list of tools to OpenAI function tool schema format."""
    return [tool_to_openai_schema(t) for t in tools]


def _extract_json_schema(tool: Any) -> dict:
    """Extract JSON Schema from a tool's args_schema."""
    args_schema = getattr(tool, "args_schema", None)

    if args_schema is None:
        return {"type": "object", "properties": {}}

    # MCPToolWrapper with raw JSON Schema via _input_schema
    if hasattr(tool, "_input_schema"):
        return tool._input_schema

    # Pydantic v2 model class
    if hasattr(args_schema, "model_json_schema"):
        schema = args_schema.model_json_schema()
        # Strip Pydantic-added fields the OpenAI tool schema doesn't want
        schema.pop("title", None)
        schema.pop("$defs", None)
        schema.pop("definitions", None)
        # Inline any $ref definitions (simple case)
        _inline_refs(schema)
        return schema

    # Pydantic v1 model class
    if hasattr(args_schema, "schema"):
        schema = args_schema.schema()
        schema.pop("title", None)
        schema.pop("definitions", None)
        return schema

    return {"type": "object", "properties": {}}


def _inline_refs(schema: dict) -> None:
    """Inline simple $ref references in properties (from Pydantic v2 $defs)."""
    defs = schema.pop("$defs", None)
    if not defs:
        return

    properties = schema.get("properties", {})
    for prop_name, prop_def in list(properties.items()):
        if "$ref" in prop_def:
            ref_name = prop_def["$ref"].split("/")[-1]
            if ref_name in defs:
                properties[prop_name] = defs[ref_name]
        # Handle anyOf (Optional types in Pydantic v2)
        if "anyOf" in prop_def:
            non_null = [t for t in prop_def["anyOf"] if t != {"type": "null"}]
            if len(non_null) == 1:
                ref = non_null[0]
                if "$ref" in ref:
                    ref_name = ref["$ref"].split("/")[-1]
                    if ref_name in defs:
                        properties[prop_name] = defs[ref_name]
