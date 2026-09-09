"""Provider-neutral message dicts stored in the checkpoint store, and their
conversion to the OpenAI Responses API input format.
"""

import json as _json
from typing import List, Optional


def build_human_message(message: str, attachments: Optional[List[dict]] = None) -> dict:
    """Build a user message dict, optionally with multi-block content for attachments."""
    if not attachments:
        return {"role": "user", "content": message}

    content_blocks = []

    # Add text content if present
    if message:
        content_blocks.append({"type": "text", "text": message})

    # Add attachment blocks
    for att in attachments:
        mime_type = att.get("mime_type", "")
        data = att.get("data", "")  # base64 encoded

        if mime_type.startswith("image/"):
            # Add text block so LLM sees the filename and file_id
            filename = att.get("filename", "image")
            file_id = att.get("file_id", "")
            file_id_str = f" | file_id: {file_id}" if file_id else ""
            content_blocks.append({
                "type": "text",
                "text": f"[Uploaded image: {filename}{file_id_str}]",
            })
            block = {
                "type": "image",
                "source": {
                    "type": "base64",
                    "media_type": mime_type,
                    "data": data,
                }
            }
            content_blocks.append(block)
        elif mime_type == "application/pdf":
            # Add text block so LLM sees the filename and file_id
            filename = att.get("filename", "document.pdf")
            file_id = att.get("file_id", "")
            file_id_str = f" | file_id: {file_id}" if file_id else ""
            content_blocks.append({
                "type": "text",
                "text": f"[Uploaded PDF: {filename}{file_id_str}]",
            })
            block = {
                "type": "document",
                "source": {
                    "type": "base64",
                    "media_type": "application/pdf",
                    "data": data,
                }
            }
            content_blocks.append(block)
        else:
            # For text-based files, include as text content
            try:
                import base64
                decoded = base64.b64decode(data).decode("utf-8")
                filename = att.get("filename", "file")
                file_id = att.get("file_id", "")
                file_id_str = f" | file_id: {file_id}" if file_id else ""
                content_blocks.append({
                    "type": "text",
                    "text": f"[Attached file: {filename}{file_id_str}]\n```\n{decoded[:10000]}\n```",
                })
            except Exception:
                filename = att.get("filename", "file")
                file_id = att.get("file_id", "")
                file_id_str = f" | file_id: {file_id}" if file_id else ""
                content_blocks.append({
                    "type": "text",
                    "text": f"[Attached file: {filename}{file_id_str} ({mime_type})]",
                })

    # If no text and no blocks, add a placeholder
    if not content_blocks:
        content_blocks.append({"type": "text", "text": "[File uploaded]"})

    return {"role": "user", "content": content_blocks}



def make_tool_result_message(tool_call_id: str, content: str) -> dict:
    """Create a tool_result message in Anthropic's format."""
    return {
        "role": "user",
        "content": [
            {
                "type": "tool_result",
                "tool_use_id": tool_call_id,
                "content": content,
            }
        ],
    }


def msg_role(m) -> str:
    """Get the role from a message dict."""
    return m.get("role", "")


def msg_content_text(m) -> str:
    """Extract text content from a message dict, handling both str and list content."""
    content = m.get("content", "")
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        parts = []
        for block in content:
            if isinstance(block, dict):
                if block.get("type") == "text":
                    parts.append(block.get("text", ""))
            else:
                parts.append(str(block))
        return "".join(parts)
    return str(content)


def is_tool_result_message(m: dict) -> bool:
    """Check if a message dict is a tool_result message."""
    content = m.get("content")
    if isinstance(content, list):
        return any(
            isinstance(block, dict) and block.get("type") == "tool_result"
            for block in content
        )
    return False


def get_tool_result_text(m: dict) -> str:
    """Extract the text content from a tool_result message."""
    content = m.get("content")
    if isinstance(content, list):
        for block in content:
            if isinstance(block, dict) and block.get("type") == "tool_result":
                result_content = block.get("content", "")
                if isinstance(result_content, str):
                    return result_content
                if isinstance(result_content, list):
                    return "".join(
                        b.get("text", "") for b in result_content
                        if isinstance(b, dict) and b.get("type") == "text"
                    )
    return ""


# ===== OPENAI MESSAGE FORMAT CONVERSION =====

def to_openai_input(messages: list) -> list:
    """Convert Anthropic-native message list to OpenAI Responses API input items.

    Handles all message types stored in the checkpoint:
    - User text messages → {"role": "user", "content": "..."}
    - User content blocks (images, PDFs) → handled with text extraction
    - User tool_result blocks → {"type": "function_call_output", ...}
    - Assistant text → {"type": "message", "role": "assistant", "content": [...]}
    - Assistant tool_use → {"type": "function_call", ...}
    """
    input_items = []

    for msg in messages:
        role = msg.get("role", "")
        content = msg.get("content", "")

        if role == "user":
            if isinstance(content, str):
                input_items.append({"role": "user", "content": content})
            elif isinstance(content, list):
                # Check for tool_result blocks
                tool_results = [b for b in content if isinstance(b, dict) and b.get("type") == "tool_result"]
                if tool_results:
                    for tr in tool_results:
                        input_items.append({
                            "type": "function_call_output",
                            "call_id": tr.get("tool_use_id", ""),
                            "output": str(tr.get("content", "")),
                        })
                else:
                    # Regular user message with content blocks — extract text
                    text_parts = []
                    for block in content:
                        if isinstance(block, dict):
                            if block.get("type") == "text":
                                text_parts.append(block.get("text", ""))
                            elif block.get("type") == "image":
                                # OpenAI vision: data URI format
                                source = block.get("source", {})
                                if source.get("type") == "base64":
                                    media_type = source.get("media_type", "image/png")
                                    data = source.get("data", "")
                                    # Add as a separate message with image content
                                    input_items.append({
                                        "role": "user",
                                        "content": [{
                                            "type": "input_image",
                                            "image_url": f"data:{media_type};base64,{data}",
                                        }],
                                    })
                            elif block.get("type") == "document":
                                # PDFs not directly supported by OpenAI — skip binary,
                                # the text annotation block is already in text_parts
                                pass
                    if text_parts:
                        input_items.append({"role": "user", "content": "\n".join(text_parts)})

        elif role == "assistant":
            if isinstance(content, str):
                input_items.append({
                    "type": "message",
                    "role": "assistant",
                    "content": [{"type": "output_text", "text": content}],
                })
            elif isinstance(content, list):
                text_parts = []
                for block in content:
                    if isinstance(block, dict):
                        if block.get("type") == "text":
                            text_parts.append(block.get("text", ""))
                        elif block.get("type") == "tool_use":
                            # Emit accumulated text as a message first
                            if text_parts:
                                input_items.append({
                                    "type": "message",
                                    "role": "assistant",
                                    "content": [{"type": "output_text", "text": "\n".join(text_parts)}],
                                })
                                text_parts = []
                            # Function call item
                            input_items.append({
                                "type": "function_call",
                                "name": block.get("name", ""),
                                "arguments": _json.dumps(block.get("input", {})),
                                "call_id": block.get("id", ""),
                            })
                if text_parts:
                    input_items.append({
                        "type": "message",
                        "role": "assistant",
                        "content": [{"type": "output_text", "text": "\n".join(text_parts)}],
                    })

    return input_items
