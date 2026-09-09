"""
Shared LLM client for Tier 2 (Haiku background) calls.

Provides a singleton AsyncAnthropic client and convenience wrappers.
Replaces ChatAnthropic + langchain_core.messages for all Haiku call sites.
"""

from typing import Optional

import anthropic

# D-001-3: background jobs stay on Claude Haiku 4.5. This module is the only Anthropic caller in the codebase; chat never uses it.
HAIKU_MODEL = "claude-haiku-4-5-20251001"

_client: Optional[anthropic.AsyncAnthropic] = None


def _get_client() -> anthropic.AsyncAnthropic:
    """Get or create the singleton Anthropic client."""
    global _client
    if _client is None:
        _client = anthropic.AsyncAnthropic()
    return _client


async def haiku_call(
    system: str,
    message: str,
    max_tokens: int = 256,
    temperature: float = 0,
    model: str = HAIKU_MODEL,
) -> str:
    """Simple Haiku call that returns text content.

    Args:
        system: System prompt text
        message: User message text
        max_tokens: Max tokens to generate
        temperature: Sampling temperature
        model: Model ID (defaults to Haiku 4.5)

    Returns:
        Response text content as a string
    """
    client = _get_client()
    response = await client.messages.create(
        model=model,
        system=system,
        messages=[{"role": "user", "content": message}],
        max_tokens=max_tokens,
        temperature=temperature,
    )
    return _extract_text(response)


async def haiku_call_with_usage(
    system: str,
    message: str,
    max_tokens: int = 256,
    temperature: float = 0,
    model: str = HAIKU_MODEL,
) -> tuple[str, int, int]:
    """Haiku call that also returns token usage.

    Returns:
        Tuple of (text, input_tokens, output_tokens)
    """
    client = _get_client()
    response = await client.messages.create(
        model=model,
        system=system,
        messages=[{"role": "user", "content": message}],
        max_tokens=max_tokens,
        temperature=temperature,
    )
    text = _extract_text(response)
    input_tokens = response.usage.input_tokens if response.usage else 0
    output_tokens = response.usage.output_tokens if response.usage else 0
    return text, input_tokens, output_tokens


def _extract_text(response) -> str:
    """Extract text from an Anthropic API response."""
    for block in response.content:
        if block.type == "text":
            return block.text
    return ""
