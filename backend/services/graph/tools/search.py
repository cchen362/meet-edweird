from services.graph.tool_decorator import tool


@tool
async def web_search(query: str, count: int = 5) -> str:
    """
    Search the web using Brave Search.

    Use this to find current information, news, or answers to questions
    that require up-to-date knowledge.

    Args:
        query: Search query string
        count: Number of results to return (1-20, default 5)

    Returns:
        Formatted search results with titles, URLs, and descriptions
    """
    from services.brave_search_service import search, is_configured

    if not is_configured():
        return "Web search not available. Brave Search API key is not configured."

    try:
        results = await search(query, count)

        if not results:
            return f"No results found for '{query}'."

        output = [f"Search results for '{query}':\n"]
        for i, result in enumerate(results, 1):
            output.append(f"{i}. **{result['title']}**")
            output.append(f"   URL: {result['url']}")
            output.append(f"   {result['description']}\n")

        return "\n".join(output)
    except Exception as e:
        return f"Search failed: {str(e)}"


@tool
async def fetch_page_content(url: str) -> str:
    """
    Fetch and extract the main content from a web page.

    Use this after web_search to get the full text of a promising result.
    Returns clean article text, stripped of navigation, ads, etc.

    Args:
        url: The URL to fetch content from

    Returns:
        Extracted text content from the page
    """
    from services.brave_search_service import fetch_page_content as fetch, is_configured

    if not is_configured():
        return "Page fetching not available. Brave Search API key is not configured."

    try:
        content = await fetch(url)
        return content
    except Exception as e:
        return f"Failed to fetch page content: {str(e)}"


# List of all search tools
SEARCH_TOOLS = [web_search, fetch_page_content]


def get_search_tools_description() -> str:
    """Get a description of available search tools for the system prompt."""
    return """
## Web Search

- **web_search**: Search via Brave Search. Returns titles, URLs, snippets.
- **fetch_page_content**: Get full text from a URL found via search.

After finding reusable results, consider saving them as a document.
"""
