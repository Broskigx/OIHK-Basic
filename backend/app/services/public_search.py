"""Public web search for OIHK Basic — simple web fetching, no external search APIs."""

from __future__ import annotations

from app.core.config import get_settings


async def search_public(query: str, max_results: int = 5) -> list[dict]:
    """Simple public web search.

    In OIHK Basic, this uses a basic web fetch approach. For production-quality
    results, configure a SearXNG instance (OIHK_SEARXNG_URL).
    """
    settings = get_settings()
    results: list[dict] = []

    if settings.searxng_url:
        try:
            return await _search_searxng(query, max_results)
        except Exception:
            pass

    if settings.brave_api_key:
        try:
            return await _search_brave(query, max_results)
        except Exception:
            pass

    return results


async def _search_searxng(query: str, max_results: int) -> list[dict]:
    """Search via SearXNG instance."""
    import httpx

    settings = get_settings()
    async with httpx.AsyncClient(timeout=15.0) as client:
        resp = await client.get(
            f"{settings.searxng_url}/search",
            params={"q": query, "format": "json", "language": "en", "categories": "general"},
            headers={"User-Agent": "OIHK-Basic/0.1.0"},
        )
        if resp.status_code == 200:
            data = resp.json()
            results = []
            for r in data.get("results", [])[:max_results]:
                results.append(
                    {
                        "title": r.get("title", ""),
                        "url": r.get("url", ""),
                        "snippet": r.get("content", ""),
                        "source_name": r.get("engine", "searxng"),
                    }
                )
            return results
    return []


async def _search_brave(query: str, max_results: int) -> list[dict]:
    """Search via Brave Search API."""
    import httpx

    settings = get_settings()
    async with httpx.AsyncClient(timeout=15.0) as client:
        resp = await client.get(
            "https://api.search.brave.com/res/v1/web/search",
            params={"q": query, "count": max_results},
            headers={
                "Accept": "application/json",
                "Accept-Encoding": "gzip",
                "X-Subscription-Token": settings.brave_api_key,
            },
        )
        if resp.status_code == 200:
            data = resp.json()
            results = []
            for r in data.get("web", {}).get("results", [])[:max_results]:
                results.append(
                    {
                        "title": r.get("title", ""),
                        "url": r.get("url", ""),
                        "snippet": r.get("description", ""),
                        "source_name": "brave",
                    }
                )
            return results
    return []
