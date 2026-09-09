"""The Tier 1 chat call over Codex OAuth (ChatGPT subscription credits)."""

import json as _json
import time
from typing import Dict, Optional

import httpx

from services.graph.messages import to_openai_input


async def call_codex(
    model: str,
    static_system: str,
    dynamic_context: str,
    messages: list,
    tool_schemas: list,
    temperature: float,
    max_tokens: int = 16384,
) -> dict:
    """Call OpenAI via Codex OAuth (ChatGPT subscription credits).

    Uses chatgpt.com/backend-api/codex/responses endpoint via raw httpx.
    ChatGPT backend REQUIRES stream=true — we collect SSE events and extract
    the full response from the terminal response event.
    Returns normalized dict: {text, tool_calls, assistant_message, raw_response}
    """
    from services.codex_oauth_service import get_access_token, get_account_id, CODEX_API_URL

    access_token = await get_access_token()
    account_id = await get_account_id()

    if not access_token or not account_id:
        raise ValueError("Codex OAuth not configured or tokens expired. Sign in again in Settings.")

    instructions = (
        static_system
        + "\n\n"
        + dynamic_context
        + "\n\n## Response Rule\nNever end a response with a hedging offer like 'If you want, I can...', 'Would you like me to...', 'Let me know if you'd like...', or any variant. You have already decided whether to act. Either do it, or say plainly that you won't and why. End responses with your answer or action — not an invitation to ask you to act."
    )
    input_items = to_openai_input(messages)

    body = {
        "model": model,
        "instructions": instructions,
        "input": input_items,
        "stream": True,  # REQUIRED by ChatGPT backend (rejects stream=false)
        "store": False,  # REQUIRED for ChatGPT backend
        "include": ["reasoning.encrypted_content"],  # REQUIRED for stateless multi-turn
        "reasoning": {"effort": "medium", "summary": "auto"},
        # NO max_output_tokens — unsupported by ChatGPT backend
    }

    if tool_schemas:
        body["tools"] = tool_schemas

    headers = {
        "Authorization": f"Bearer {access_token}",
        "ChatGPT-Account-Id": account_id,
        "originator": "edward",
        "OpenAI-Beta": "responses=experimental",
        "Content-Type": "application/json",
    }

    # Stream SSE and collect delta events plus the terminal response event.
    # OpenAI may return an empty output[] in response.completed, so we accumulate
    # content from delta events as the primary source of truth.
    completed_data = None
    terminal_event_name = None
    # Separate timeouts: 30s connect, 90s between chunks (read), 30s write/pool
    # The read timeout resets per chunk — handles slow reasoning without false timeout.
    stream_timeout = httpx.Timeout(connect=30.0, read=90.0, write=30.0, pool=30.0)
    # Hard cap: 300s total wall-clock time to prevent infinite hangs (extended thinking can take 3–4 minutes)
    CODEX_TOTAL_TIMEOUT = 300.0
    stream_start = time.monotonic()
    event_counts: Dict[str, int] = {}
    last_event_time = stream_start

    # Accumulate streamed content by item_id (in case response.completed has empty output)
    # item_id -> {"type": "message"|"function_call", "text": str, "args": str, "call_id": str, "name": str}
    _streamed_items: Dict[str, dict] = {}
    # Track item order for correct output reconstruction
    _item_order: list = []

    async with httpx.AsyncClient(timeout=stream_timeout) as client:
        async with client.stream("POST", CODEX_API_URL, json=body, headers=headers) as response:
            if response.status_code == 404:
                body_text = ""
                async for chunk in response.aiter_text():
                    body_text += chunk
                if "usage_limit_reached" in body_text:
                    raise ValueError("ChatGPT usage limit reached. Try again later.")
                raise ValueError(f"Codex API returned 404: {body_text[:200]}")

            if response.status_code == 401:
                raise ValueError("Codex OAuth token expired or invalid. Sign in again in Settings.")

            if response.status_code != 200:
                body_text = ""
                async for chunk in response.aiter_text():
                    body_text += chunk
                raise ValueError(f"Codex API error ({response.status_code}): {body_text[:200]}")

            print(f"[CODEX] Stream connected, waiting for response...")

            # Parse SSE stream — accumulate deltas AND capture terminal event.
            # SSE format: "event: <type>\ndata: <json>\n\n"
            # Data can span multiple "data:" lines (concatenated with \n per SSE spec)
            buffer = ""
            current_event = ""
            current_data_lines = []
            async for chunk in response.aiter_text():
                # Check total wall-clock timeout
                elapsed = time.monotonic() - stream_start
                if elapsed > CODEX_TOTAL_TIMEOUT:
                    _codex_log_summary(event_counts, elapsed, "TIMEOUT")
                    raise ValueError(f"Codex API total timeout ({CODEX_TOTAL_TIMEOUT:.0f}s) exceeded. Try again later.")

                buffer += chunk
                while "\n" in buffer:
                    line, buffer = buffer.split("\n", 1)
                    line = line.rstrip("\r")

                    if line.startswith("event: "):
                        current_event = line[7:]
                        current_data_lines = []
                    elif line.startswith("data: "):
                        current_data_lines.append(line[6:])
                    elif line == "":
                        # Blank line = event dispatch (per SSE spec)
                        if current_event and current_data_lines:
                            event_counts[current_event] = event_counts.get(current_event, 0) + 1
                            last_event_time = time.monotonic()
                            data_str = "\n".join(current_data_lines)
                            if data_str.strip():
                                try:
                                    evt_data = _json.loads(data_str)
                                except _json.JSONDecodeError:
                                    evt_data = None

                                if current_event in {"response.completed", "response.done"} and evt_data is not None:
                                    completed_data = evt_data
                                    terminal_event_name = current_event

                                elif current_event == "error" and evt_data is not None:
                                    error_msg = evt_data.get("error", {}).get("message", data_str[:200])
                                    _codex_log_summary(event_counts, time.monotonic() - stream_start, "ERROR")
                                    raise ValueError(f"Codex API stream error: {error_msg}")

                                elif current_event == "response.output_item.added" and evt_data is not None:
                                    # Register a new output item: captures type, name, call_id for function calls
                                    item = evt_data.get("item", {})
                                    item_id = item.get("id", "")
                                    if item_id and item_id not in _streamed_items:
                                        item_type = item.get("type", "")
                                        _streamed_items[item_id] = {
                                            "type": item_type,
                                            "text": "",
                                            "args": "",
                                            "call_id": item.get("call_id", ""),
                                            "name": item.get("name", ""),
                                        }
                                        _item_order.append(item_id)

                                elif current_event == "response.output_text.delta" and evt_data is not None:
                                    item_id = evt_data.get("item_id", "")
                                    delta = evt_data.get("delta", "")
                                    if item_id:
                                        if item_id not in _streamed_items:
                                            _streamed_items[item_id] = {"type": "message", "text": "", "args": "", "call_id": "", "name": ""}
                                            _item_order.append(item_id)
                                        _streamed_items[item_id]["text"] += delta

                                elif current_event == "response.function_call_arguments.delta" and evt_data is not None:
                                    item_id = evt_data.get("item_id", "")
                                    delta = evt_data.get("delta", "")
                                    if item_id:
                                        if item_id not in _streamed_items:
                                            _streamed_items[item_id] = {"type": "function_call", "text": "", "args": "", "call_id": "", "name": ""}
                                            _item_order.append(item_id)
                                        _streamed_items[item_id]["args"] += delta

                        current_event = ""
                        current_data_lines = []

    elapsed = time.monotonic() - stream_start

    # Handle edge case: stream ends without trailing blank line after last event
    if not completed_data and current_event in {"response.completed", "response.done"} and current_data_lines:
        data_str = "\n".join(current_data_lines)
        if data_str.strip():
            try:
                completed_data = _json.loads(data_str)
                terminal_event_name = current_event
            except _json.JSONDecodeError:
                pass

    if not completed_data:
        partial_event_count = sum(
            count
            for event_name, count in event_counts.items()
            if event_name.startswith("response.output")
            or event_name.startswith("response.function_call")
        )
        status = "NO_TERMINAL_PARTIAL" if partial_event_count else "NO_TERMINAL"
        _codex_log_summary(event_counts, elapsed, status)
        if partial_event_count:
            raise ValueError(
                "Codex API stream ended after partial output or tool-call events without a terminal response event."
            )
        raise ValueError("Codex API stream ended without response.done or response.completed.")

    # If response.completed has an empty output array, reconstruct from accumulated deltas.
    # This handles the case where OpenAI no longer populates output[] in the terminal event.
    _resp_obj = completed_data if "output" in completed_data else completed_data.get("response", completed_data)
    if not _resp_obj.get("output") and _streamed_items:
        reconstructed_output = []
        for item_id in _item_order:
            item_data = _streamed_items[item_id]
            if item_data["type"] == "function_call":
                reconstructed_output.append({
                    "type": "function_call",
                    "id": item_id,
                    "call_id": item_data["call_id"],
                    "name": item_data["name"],
                    "arguments": item_data["args"],
                })
            elif item_data["text"]:
                reconstructed_output.append({
                    "type": "message",
                    "id": item_id,
                    "role": "assistant",
                    "status": "completed",
                    "content": [{"type": "output_text", "text": item_data["text"], "annotations": []}],
                })
        if reconstructed_output:
            _resp_obj["output"] = reconstructed_output
            print(f"[CODEX] Reconstructed output from deltas: {len(reconstructed_output)} items")

    _codex_log_summary(event_counts, elapsed, "OK", terminal_event_name=terminal_event_name)
    return _parse_codex_response(completed_data)


def _codex_log_summary(
    event_counts: Dict[str, int],
    elapsed: float,
    status: str,
    terminal_event_name: Optional[str] = None,
):
    """Log a one-line summary of a Codex SSE stream."""
    total = sum(event_counts.values())
    parts = [f"{v} {k}" for k, v in sorted(event_counts.items(), key=lambda x: -x[1])]
    summary = ", ".join(parts[:5])  # Top 5 event types
    if len(parts) > 5:
        summary += f", +{len(parts) - 5} more types"
    terminal_suffix = f", terminal={terminal_event_name}" if terminal_event_name else ""
    print(
        f"[CODEX] Stream {status}{terminal_suffix} in {elapsed:.1f}s ({total} events: {summary})"
        if total
        else f"[CODEX] Stream {status}{terminal_suffix} in {elapsed:.1f}s (0 events)"
    )


def _parse_codex_response(data: dict) -> dict:
    """Parse raw Codex/OpenAI JSON response into normalized format.

    Handles both direct response objects and potentially nested structures
    (e.g. {"response": {actual response}}) from the Codex SSE endpoint.
    Converts to Anthropic-native assistant_message format for checkpoint storage.
    """
    # Handle potential nesting: some SSE endpoints wrap the response under a key
    if "output" not in data and isinstance(data.get("response"), dict):
        data = data["response"]

    text_parts = []
    tool_calls = []
    content_blocks = []

    for item in data.get("output", []):
        item_type = item.get("type", "")

        if item_type == "message":
            for content in item.get("content", []):
                if content.get("type") == "output_text":
                    text = content.get("text", "")
                    text_parts.append(text)
                    content_blocks.append({"type": "text", "text": text})

        elif item_type == "function_call":
            args_raw = item.get("arguments", "{}")
            if isinstance(args_raw, str):
                try:
                    args = _json.loads(args_raw)
                except _json.JSONDecodeError:
                    args = {}
            else:
                args = args_raw

            tc = {
                "id": item.get("call_id", ""),
                "name": item.get("name", ""),
                "args": args,
            }
            tool_calls.append(tc)
            content_blocks.append({
                "type": "tool_use",
                "id": tc["id"],
                "name": tc["name"],
                "input": tc["args"],
            })

    full_text = "".join(text_parts)

    # Fallback: use the top-level output_text convenience field if we didn't
    # find text in the output array (handles unexpected response shapes)
    if not full_text and not tool_calls and data.get("output_text"):
        full_text = data["output_text"]
        content_blocks.append({"type": "text", "text": full_text})

    return {
        "text": full_text,
        "tool_calls": tool_calls,
        "assistant_message": {"role": "assistant", "content": content_blocks},
        "raw_response": data,
    }


# D-001-2: chat is GPT via Codex OAuth only. No Anthropic chat path, no metered OpenAI API-key fallback — a rejected model must surface as an error, never as silent spend.
async def call_llm(
    model: str,
    static_system: str,
    dynamic_context: str,
    messages: list,
    tool_schemas: list,
    temperature: float,
    max_tokens: int = 16384,
) -> dict:
    """Call GPT through the Codex OAuth endpoint (ChatGPT subscription credits).

    `model` is resolved against the models the Codex endpoint currently serves
    before the call is made, so a stale or rejected model id never reaches the
    API silently — resolve_chat_model() raises if Codex OAuth is not connected.

    Returns normalized dict: {text, tool_calls, assistant_message, raw_response}
    """
    from services.codex_oauth_service import resolve_chat_model

    model = await resolve_chat_model(model)
    print(f"[LLM] Calling Codex OAuth ({model})")
    return await call_codex(model, static_system, dynamic_context, messages, tool_schemas, temperature, max_tokens)
