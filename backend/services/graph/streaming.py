"""One chat turn: retrieve memories, call the model, run tools, stream events.

The system prompt lives in `services/graph/prompt.py`, the SSE event contract
in `services/graph/events.py`, provider-neutral message handling in
`services/graph/messages.py`, the Codex OAuth call in `services/graph/codex.py`,
and tool execution in `services/graph/tool_execution.py`. This module wires
those pieces into the two turn loops: the streaming path used by the chat
router, and a non-streaming variant used by the scheduler and WhatsApp triage.
"""

import asyncio
import hashlib
import json as _json
from datetime import datetime
from typing import AsyncGenerator, List, Any, Dict, Optional

from services.tool_registry import get_available_tools
from services.graph.tool_schema import tools_to_openai_schemas
from services.graph.prompt import (
    MAX_NORMAL_MEMORIES,
    MAX_ENRICHED_MEMORIES,
    EDWARD_CHARACTER,
    build_memory_context,
)
from services.graph.events import EventType, create_event, tool_label
from services.graph.messages import (
    build_human_message,
    make_tool_result_message,
    msg_role,
    msg_content_text,
    is_tool_result_message,
    get_tool_result_text,
)
from services.graph.codex import call_llm
from services.graph.tool_execution import execute_tool_call, execute_tool_call_with_events

# Tool call loop bounds
MAX_TOOL_ITERATIONS = 30
MAX_CONSECUTIVE_ERROR_ITERATIONS = 3


async def stream_with_memory_events(
    message: str,
    conversation_id: str,
    system_prompt: str,
    model: str,
    temperature: float,
    attachments: Optional[List[dict]] = None,
) -> AsyncGenerator[Dict[str, Any], None]:
    """Stream a response with structured events while maintaining conversation memory."""
    from services.memory_service import retrieve_memories, extract_and_store_memories, Memory
    from services.graph.tools.context import set_current_conversation_id
    from services.checkpoint_store import get_messages, save_messages
    assistant_content_emitted = False

    # Set the conversation ID so tools can find the current conversation
    set_current_conversation_id(conversation_id)

    # Load existing messages from checkpoint store
    messages = await get_messages(conversation_id)

    # Add the new user message (with attachments if present)
    messages.append(build_human_message(message, attachments))

    # ===== MEMORY RETRIEVAL (with deep retrieval gate) =====
    # Emit progress event for memory search
    yield create_event(EventType.PROGRESS, conversation_id,
        step="memory_search",
        status="started",
        message="Searching memory..."
    )

    turn_count = sum(1 for m in messages if msg_role(m) == "user")
    retrieved_memories: List[Memory] = []
    try:
        from services.deep_retrieval_service import should_deep_retrieve, deep_retrieve_memories
        if await should_deep_retrieve(message, conversation_id, turn_count):
            # Format recent messages for Haiku query generation
            recent_msgs = [
                {"role": "human" if msg_role(m) == "user" else "assistant",
                 "content": msg_content_text(m)}
                for m in messages[-5:]
                if msg_role(m) in ("user", "assistant")
            ]
            try:
                retrieved_memories = await asyncio.wait_for(
                    deep_retrieve_memories(message, recent_msgs, limit=MAX_NORMAL_MEMORIES),
                    timeout=10.0,
                )
            except (asyncio.TimeoutError, Exception) as e:
                print(f"Deep retrieval failed, falling back to normal: {e}")
                retrieved_memories = await retrieve_memories(message, limit=MAX_NORMAL_MEMORIES)
        else:
            retrieved_memories = await retrieve_memories(message, limit=MAX_NORMAL_MEMORIES)
        yield create_event(EventType.PROGRESS, conversation_id,
            step="memory_search",
            status="completed",
            message=f"Found {len(retrieved_memories)} memories" if retrieved_memories else "No relevant memories",
            count=len(retrieved_memories)
        )
    except Exception as e:
        print(f"Memory retrieval failed: {e}")
        yield create_event(EventType.PROGRESS, conversation_id,
            step="memory_search",
            status="error",
            message="Memory search failed"
        )

    # ===== ENRICHMENT LOADING (from previous reflection) =====
    enriched_memories = []
    try:
        from services.reflection_service import load_enrichments
        enriched_memories = await load_enrichments(conversation_id, limit=MAX_ENRICHED_MEMORIES)
        if enriched_memories:
            print(f"[ENRICHMENT] Loaded {len(enriched_memories)} enrichments for {conversation_id}")
    except Exception as e:
        print(f"Enrichment loading failed: {e}")

    # ===== DOCUMENT RETRIEVAL =====
    relevant_documents = []
    try:
        from services.document_service import retrieve_relevant_documents
        relevant_documents = await retrieve_relevant_documents(message, limit=3)
    except Exception as e:
        print(f"Document retrieval failed: {e}")

    # ===== HEARTBEAT BRIEFING =====
    briefing_context = ""
    try:
        from services.heartbeat.heartbeat_service import get_pending_briefing
        briefing = await get_pending_briefing()
        if briefing:
            briefing_context = f"\n\n## Recent Awareness\nWhile you were away, you noticed:\n{briefing}"
    except Exception as e:
        print(f"Heartbeat briefing failed: {e}")

    # ===== TOOL SELECTION =====
    tools = await get_available_tools()

    # Build enhanced system prompt with memories, tool descriptions, and current time
    memory_context = build_memory_context(
        retrieved_memories, tools=tools, documents=relevant_documents,
        enriched_memories=enriched_memories,
    )
    now = datetime.now()
    time_context = f"\n\nCurrent date and time: {now.strftime('%A, %B %d, %Y at %I:%M %p')}"
    # Split system prompt into static (cacheable) and dynamic (per-turn) parts
    static_system = (
        system_prompt
        + EDWARD_CHARACTER
    )
    dynamic_context = memory_context + briefing_context + time_context

    # Build tool schemas (OpenAI Responses API format — the only format now needed)
    tool_schemas = tools_to_openai_schemas(tools) if tools else []

    full_response = ""
    tool_calls_made = []
    needs_streaming = True

    # Track repeated failures: "tool_name:args_hash" -> count
    _failure_tracker: Dict[str, int] = {}
    # Track consecutive iterations where ALL tool calls fail
    consecutive_error_iterations = 0

    # Tool call loop
    iteration = 0

    # Track whether a fatal LLM error occurred (to skip post-processing)
    _llm_error_occurred = False

    while iteration < MAX_TOOL_ITERATIONS:
        iteration += 1

        # Emit thinking event when processing
        if iteration > 1:
            yield create_event(EventType.THINKING, conversation_id, content="Thinking...")

        # Emit "Generating response..." BEFORE the model call (visible while model thinks)
        yield create_event(EventType.PROGRESS, conversation_id,
            step="generating",
            status="started",
            message="Generating response..."
        )

        # Keepalive heartbeat: yield progress updates every 5s while waiting for model
        _llm_task = asyncio.ensure_future(call_llm(
            model, static_system, dynamic_context, messages, tool_schemas, temperature,
        ))
        _KEEPALIVE_INTERVAL = 5.0
        _elapsed_s = 0.0
        try:
            while True:
                try:
                    result = await asyncio.wait_for(asyncio.shield(_llm_task), timeout=_KEEPALIVE_INTERVAL)
                    break
                except asyncio.TimeoutError:
                    _elapsed_s += _KEEPALIVE_INTERVAL
                    yield create_event(EventType.PROGRESS, conversation_id,
                        step="generating",
                        status="started",
                        message=f"Generating response... ({int(_elapsed_s)}s)"
                    )
        except Exception as e:
            _llm_task.cancel()
            error_msg = str(e)
            print(f"[LLM ERROR] {error_msg}")
            yield create_event(EventType.ERROR, conversation_id, error=error_msg)
            full_response = f"I encountered an error: {error_msg}"
            assistant_content_emitted = True
            yield create_event(EventType.CONTENT, conversation_id, content=full_response)
            needs_streaming = False
            _llm_error_occurred = True
            break

        # Extract tool calls from normalized result
        response_tool_calls = result["tool_calls"]

        # Check if there are tool calls
        if response_tool_calls:
            # Add the assistant message (always Anthropic-native format for storage)
            messages.append(result["assistant_message"])

            # Execute each tool call with event streaming
            for tool_call in response_tool_calls:
                tool_calls_made.append(tool_call)

                # Circuit breaker: block repeated identical failures
                failure_key = f"{tool_call['name']}:{hashlib.md5(_json.dumps(tool_call.get('args', {}), sort_keys=True).encode()).hexdigest()}"
                if _failure_tracker.get(failure_key, 0) >= 1:
                    tool_result = f"BLOCKED: {tool_call['name']} already failed with these arguments. Fix the arguments or use a different approach."
                    print(f"[CIRCUIT BREAKER] Blocked repeated failure: {tool_call['name']}")
                    # Emit events so the UI shows the blocked call instead of going silent
                    yield create_event(EventType.TOOL_START, conversation_id, tool_name=tool_call['name'])
                    yield create_event(EventType.TOOL_END, conversation_id, tool_name=tool_call['name'], result=tool_result)
                    messages.append(make_tool_result_message(tool_call['id'], tool_result))
                    continue

                # Emit progress event for tool execution
                yield create_event(EventType.PROGRESS, conversation_id,
                    step="tool_execution",
                    status="started",
                    message=tool_label(tool_call['name']),
                    tool_name=tool_call['name']
                )

                # Stream events from tool execution
                tool_result = None
                async for event in execute_tool_call_with_events(tool_call, tools, conversation_id):
                    if "_result" in event:
                        tool_result = event["_result"]
                    else:
                        yield event

                # Track failures for circuit breaker
                if str(tool_result).startswith("Tool error:"):
                    _failure_tracker[failure_key] = _failure_tracker.get(failure_key, 0) + 1

                # Emit progress event for tool completion
                yield create_event(EventType.PROGRESS, conversation_id,
                    step="tool_execution",
                    status="completed",
                    message=tool_label(tool_call['name']),
                    tool_name=tool_call['name']
                )

                print(f"Tool {tool_call['name']} result: {str(tool_result)[:200]}..." if len(str(tool_result)) > 200 else f"Tool {tool_call['name']} result: {tool_result}")

                # Add tool result as a message
                messages.append(make_tool_result_message(tool_call['id'], str(tool_result)))

            # Track consecutive all-failed iterations
            # Check the last N tool_result messages (where N = number of tool calls this iteration)
            recent_results = messages[-len(response_tool_calls):]
            iteration_had_success = any(
                not get_tool_result_text(m).startswith("Tool error:")
                and not get_tool_result_text(m).startswith("BLOCKED:")
                for m in recent_results
                if msg_role(m) == "user" and is_tool_result_message(m)
            )
            if iteration_had_success:
                consecutive_error_iterations = 0
            else:
                consecutive_error_iterations += 1
                print(f"[TOOL LOOP] Consecutive all-failed iterations: {consecutive_error_iterations}")

            if consecutive_error_iterations >= MAX_CONSECUTIVE_ERROR_ITERATIONS:
                print(f"[TOOL LOOP] Breaking after {consecutive_error_iterations} consecutive all-failed iterations")
                break

            # GPT models can return text alongside tool calls — capture it as the final response
            if result["text"] and not full_response:
                full_response = result["text"]
                assistant_content_emitted = True
                yield create_event(EventType.CONTENT, conversation_id, content=full_response)
                needs_streaming = False

            # Continue loop to allow more tool calls
            continue
        else:
            # No more tool calls — use this response's content
            if result["text"]:
                full_response = result["text"]
                assistant_content_emitted = True
                yield create_event(EventType.CONTENT, conversation_id, content=full_response)
                needs_streaming = False
            yield create_event(EventType.PROGRESS, conversation_id,
                step="generating",
                status="completed",
                message="Response complete"
            )
            break

    # Only stream a new response if the loop didn't produce one
    if needs_streaming and not _llm_error_occurred:
        if tool_calls_made:
            # Tools executed successfully but LLM returned no final text — this is valid
            # (GPT models return function_call without accompanying text, unlike Claude)
            tool_summary = ", ".join(sorted(set(tc["name"] for tc in tool_calls_made)))
            full_response = f"[Completed: {tool_summary}]"
            assistant_content_emitted = True
            yield create_event(EventType.CONTENT, conversation_id, content=full_response)
        else:
            print(f"[WARNING] Tool loop exited after {iteration}/{MAX_TOOL_ITERATIONS} iterations without final response, streaming new response")
            fallback_static = static_system + "\n\nYou have used all available tool iterations. Summarize what you accomplished and respond to the user. Do not attempt any more tool calls."
            # Non-streaming fallback (Codex Responses API streaming is complex to redo mid-loop)
            fallback_result = await call_llm(
                model, fallback_static, dynamic_context, messages, [], temperature,
            )
            full_response = fallback_result["text"]
            if full_response:
                assistant_content_emitted = True
                yield create_event(EventType.CONTENT, conversation_id, content=full_response)

    # Safety net: if no content was ever produced, send a plain fallback
    if not full_response.strip():
        full_response = "I completed the requested actions. Let me know if you need anything else!"
        assistant_content_emitted = True
        yield create_event(EventType.CONTENT, conversation_id, content=full_response)

    # Add assistant response to messages
    messages.append({"role": "assistant", "content": full_response})

    # Save conversation state to checkpoint store
    try:
        await save_messages(conversation_id, messages, metadata={
            "system_prompt": system_prompt,
            "model": model,
            "temperature": temperature,
            "current_response": full_response,
            "tool_calls": [
                {"name": tc["name"], "args": tc["args"]}
                for tc in tool_calls_made
            ] if tool_calls_made else [],
        })
    except Exception as e:
        error_msg = f"Failed to save conversation state: {e}"
        print(f"[STREAM ERROR] {error_msg}")
        yield create_event(EventType.ERROR, conversation_id, error=error_msg)
        if not assistant_content_emitted:
            assistant_content_emitted = True
            yield create_event(
                EventType.CONTENT,
                conversation_id,
                content="I encountered an error before I could finish the response. Please try again.",
            )
        yield create_event(EventType.DONE, conversation_id)
        return

    # ===== DONE EVENT — generator exhausts here, HTTP connection closes immediately =====
    yield create_event(EventType.DONE, conversation_id)

    # ===== MEMORY EXTRACTION (true fire-and-forget via create_task) =====
    # IMPORTANT: must use create_task, not await — the generator must fully exhaust
    # after yield DONE so FastAPI closes the HTTP response immediately. On Ngrok,
    # awaiting here keeps the connection open and Ngrok's tunnel timeout can drop it
    # before the browser confirms receipt of the done event.
    if not _llm_error_occurred:
        async def _post_turn_work():
            try:
                messages_for_extraction = [
                    {"role": "human" if msg_role(m) == "user" else "assistant",
                     "content": msg_content_text(m)}
                    for m in messages[-10:]
                    if msg_role(m) in ("user", "assistant")
                ]
                await asyncio.wait_for(
                    extract_and_store_memories(
                        messages=messages_for_extraction,
                        conversation_id=conversation_id,
                        existing_memories=retrieved_memories
                    ),
                    timeout=30,
                )

                # Fire-and-forget search tag generation
                from services.search_tag_service import generate_search_tags_safe
                asyncio.create_task(generate_search_tags_safe(conversation_id, messages_for_extraction))

                # Fire-and-forget reflection for next turn's enrichment
                try:
                    from services.reflection_service import should_reflect, run_reflection_safe
                    if should_reflect(messages_for_extraction, turn_count):
                        asyncio.create_task(run_reflection_safe(
                            conversation_id, messages_for_extraction,
                            [m.id for m in retrieved_memories]
                        ))
                except Exception as e:
                    print(f"Reflection fire-and-forget failed: {e}")
            except asyncio.TimeoutError:
                print(f"Memory extraction timed out after 30s for conversation {conversation_id}")
            except Exception as e:
                print(f"Memory extraction failed: {e}")

        asyncio.create_task(_post_turn_work())


async def chat_with_memory(
    message: str,
    conversation_id: str,
    system_prompt: str,
    model: str,
    temperature: float,
    attachments: Optional[List[dict]] = None,
) -> str:
    """Get a non-streaming response while maintaining conversation memory."""
    from services.memory_service import retrieve_memories, extract_and_store_memories, Memory
    from services.checkpoint_store import get_messages, save_messages

    # Load existing messages from checkpoint store
    messages = await get_messages(conversation_id)

    # Add the new user message (with attachments if present)
    messages.append(build_human_message(message, attachments))

    # ===== MEMORY RETRIEVAL (with deep retrieval gate) =====
    turn_count = sum(1 for m in messages if msg_role(m) == "user")
    retrieved_memories: List[Memory] = []
    enriched_memories = []
    relevant_documents = []

    try:
        from services.deep_retrieval_service import should_deep_retrieve, deep_retrieve_memories
        if await should_deep_retrieve(message, conversation_id, turn_count):
            recent_msgs = [
                {"role": "human" if msg_role(m) == "user" else "assistant",
                 "content": msg_content_text(m)}
                for m in messages[-5:]
                if msg_role(m) in ("user", "assistant")
            ]
            try:
                retrieved_memories = await asyncio.wait_for(
                    deep_retrieve_memories(message, recent_msgs, limit=MAX_NORMAL_MEMORIES),
                    timeout=10.0,
                )
            except (asyncio.TimeoutError, Exception) as e:
                print(f"Deep retrieval failed, falling back to normal: {e}")
                retrieved_memories = await retrieve_memories(message, limit=MAX_NORMAL_MEMORIES)
        else:
            retrieved_memories = await retrieve_memories(message, limit=MAX_NORMAL_MEMORIES)
    except Exception as e:
        print(f"Memory retrieval failed: {e}")

    # ===== ENRICHMENT LOADING (from previous reflection) =====
    try:
        from services.reflection_service import load_enrichments
        enriched_memories = await load_enrichments(conversation_id, limit=MAX_ENRICHED_MEMORIES)
        if enriched_memories:
            print(f"[ENRICHMENT] Loaded {len(enriched_memories)} enrichments for {conversation_id}")
    except Exception as e:
        print(f"Enrichment loading failed: {e}")

    # ===== DOCUMENT RETRIEVAL =====
    try:
        from services.document_service import retrieve_relevant_documents
        relevant_documents = await retrieve_relevant_documents(message, limit=3)
    except Exception as e:
        print(f"Document retrieval failed: {e}")

    # ===== HEARTBEAT BRIEFING (non-streaming) =====
    briefing_context_sync = ""
    try:
        from services.heartbeat.heartbeat_service import get_pending_briefing
        briefing_sync = await get_pending_briefing()
        if briefing_sync:
            briefing_context_sync = f"\n\n## Recent Awareness\nWhile you were away, you noticed:\n{briefing_sync}"
    except Exception as e:
        print(f"Heartbeat briefing failed: {e}")

    # ===== TOOL SELECTION =====
    tools = await get_available_tools()

    # Build enhanced system prompt with memories, tool descriptions, and current time
    memory_context = build_memory_context(
        retrieved_memories, tools=tools, documents=relevant_documents,
        enriched_memories=enriched_memories,
    )
    now = datetime.now()
    time_context = f"\n\nCurrent date and time: {now.strftime('%A, %B %d, %Y at %I:%M %p')}"
    # Split system prompt into static (cacheable) and dynamic (per-turn) parts
    static_system = (
        system_prompt
        + EDWARD_CHARACTER
    )
    dynamic_context = memory_context + briefing_context_sync + time_context

    # Build tool schemas (OpenAI Responses API format — the only format now needed)
    tool_schemas = tools_to_openai_schemas(tools) if tools else []

    full_response = ""
    tool_calls_made = []

    # Track repeated failures: "tool_name:args_hash" -> count
    _failure_tracker: Dict[str, int] = {}
    # Track consecutive iterations where ALL tool calls fail
    consecutive_error_iterations = 0

    # Tool call loop
    iteration = 0

    while iteration < MAX_TOOL_ITERATIONS:
        iteration += 1

        # Call the chat model
        result = await call_llm(
            model, static_system, dynamic_context, messages,
            tool_schemas, temperature,
        )

        # Extract tool calls from normalized result
        response_tool_calls = result["tool_calls"]

        # Check if there are tool calls
        if response_tool_calls:
            # Add the assistant message (always Anthropic-native format for storage)
            messages.append(result["assistant_message"])

            # Execute each tool call
            for tool_call in response_tool_calls:
                tool_calls_made.append(tool_call)

                # Circuit breaker: block repeated identical failures
                failure_key = f"{tool_call['name']}:{hashlib.md5(_json.dumps(tool_call.get('args', {}), sort_keys=True).encode()).hexdigest()}"
                if _failure_tracker.get(failure_key, 0) >= 1:
                    tool_result = f"BLOCKED: {tool_call['name']} already failed with these arguments. Fix the arguments or use a different approach."
                    print(f"[CIRCUIT BREAKER] Blocked repeated failure: {tool_call['name']}")
                    messages.append(make_tool_result_message(tool_call['id'], tool_result))
                    continue

                tool_result = await execute_tool_call(tool_call, tools)

                # Track failures for circuit breaker
                if str(tool_result).startswith("Tool error:"):
                    _failure_tracker[failure_key] = _failure_tracker.get(failure_key, 0) + 1

                print(f"Tool {tool_call['name']} result: {tool_result[:200]}..." if len(str(tool_result)) > 200 else f"Tool {tool_call['name']} result: {tool_result}")

                # Add tool result as a message
                messages.append(make_tool_result_message(tool_call['id'], str(tool_result)))

            # Track consecutive all-failed iterations
            recent_results = messages[-len(response_tool_calls):]
            iteration_had_success = any(
                not get_tool_result_text(m).startswith("Tool error:")
                and not get_tool_result_text(m).startswith("BLOCKED:")
                for m in recent_results
                if msg_role(m) == "user" and is_tool_result_message(m)
            )
            if iteration_had_success:
                consecutive_error_iterations = 0
            else:
                consecutive_error_iterations += 1
                print(f"[TOOL LOOP] Consecutive all-failed iterations: {consecutive_error_iterations}")

            if consecutive_error_iterations >= MAX_CONSECUTIVE_ERROR_ITERATIONS:
                print(f"[TOOL LOOP] Breaking after {consecutive_error_iterations} consecutive all-failed iterations")
                break

            # GPT models can return text alongside tool calls — capture it as the final response
            if result["text"] and not full_response:
                full_response = result["text"]

            # Continue loop to allow more tool calls
            continue
        else:
            # No more tool calls — use this response
            full_response = result["text"]
            break

    # If we exhausted iterations, get final response without tools
    if not full_response:
        if tool_calls_made:
            # Tools executed successfully but LLM returned no final text — this is valid
            # (GPT models return function_call without accompanying text, unlike Claude)
            tool_summary = ", ".join(sorted(set(tc["name"] for tc in tool_calls_made)))
            full_response = f"[Completed: {tool_summary}]"
        else:
            print(f"[WARNING] Tool loop exited after {iteration} iterations without final response, invoking fallback")
            fallback_static = static_system + "\n\nYou have used all available tool iterations. Summarize what you accomplished and respond to the user. Do not attempt any more tool calls."
            fallback_result = await call_llm(
                model, fallback_static, dynamic_context, messages, [], temperature,
            )
            full_response = fallback_result["text"]

    # Add assistant response to messages
    messages.append({"role": "assistant", "content": full_response})

    # Save conversation state to checkpoint store
    await save_messages(conversation_id, messages, metadata={
        "system_prompt": system_prompt,
        "model": model,
        "temperature": temperature,
        "current_response": full_response,
        "tool_calls": [
            {"name": tc["name"], "args": tc["args"]}
            for tc in tool_calls_made
        ] if tool_calls_made else [],
    })

    # ===== MEMORY EXTRACTION =====
    try:
        messages_for_extraction = [
            {"role": "human" if msg_role(m) == "user" else "assistant",
             "content": msg_content_text(m)}
            for m in messages[-10:]
            if msg_role(m) in ("user", "assistant")
        ]
        await extract_and_store_memories(
            messages=messages_for_extraction,
            conversation_id=conversation_id,
            existing_memories=retrieved_memories
        )

        # Fire-and-forget search tag generation
        from services.search_tag_service import generate_search_tags_safe
        asyncio.create_task(generate_search_tags_safe(conversation_id, messages_for_extraction))

        # Fire-and-forget reflection for next turn's enrichment
        try:
            from services.reflection_service import should_reflect, run_reflection_safe
            if should_reflect(messages_for_extraction, turn_count):
                asyncio.create_task(run_reflection_safe(
                    conversation_id, messages_for_extraction,
                    [m.id for m in retrieved_memories]
                ))
        except Exception as e:
            print(f"Reflection fire-and-forget failed: {e}")
    except Exception as e:
        print(f"Memory extraction failed: {e}")

    return full_response
