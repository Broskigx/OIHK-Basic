"""Public web search for OIHK Basic — simple web fetching, no external search APIs."""

from __future__ import annotations

import logging
from urllib.parse import urlsplit, urlunsplit

from app.core.config import get_settings
from app.services.safe_http import get_json_bounded
from app.version import PRODUCT_VERSION

logger = logging.getLogger(__name__)


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
            logger.warning("SearXNG search failed for query %r; falling back", query, exc_info=True)

    if settings.brave_api_key:
        try:
            return await _search_brave(query, max_results)
        except Exception:
            logger.warning("Brave search failed for query %r; returning empty results", query, exc_info=True)

    return results


def _searxng_search_url(configured: str) -> str:
    """Validate the operator-configured SearXNG base URL.

    The value arrives from configuration rather than a request, but an
    unvalidated base still lets a typo or a stray scheme send the query
    somewhere unintended, so it is checked before every use.
    """
    parsed = urlsplit(configured.strip())
    if parsed.scheme not in {"http", "https"} or not parsed.hostname:
        raise ValueError("OIHK_SEARXNG_URL must be an http(s) URL.")
    if parsed.username or parsed.password:
        raise ValueError("OIHK_SEARXNG_URL must not embed credentials.")
    # Trim the trailing slash from the *path*, not from the configured string.
    # A value carrying a query or fragment does not end in "/" no matter how
    # it was written, so trimming the whole string left the path as "/" and
    # produced "//search". Any query and fragment are dropped here as well:
    # only the base belongs in the URL this builds, and a configured query
    # string would otherwise merge with the search parameters set below.
    path = parsed.path.rstrip("/")
    return urlunsplit((parsed.scheme, parsed.netloc, f"{path}/search", "", ""))


async def _search_searxng(query: str, max_results: int) -> list[dict]:
    """Search via SearXNG instance."""
    import httpx

    settings = get_settings()
    async with httpx.AsyncClient(timeout=15.0) as client:
        data = await get_json_bounded(
            client,
            _searxng_search_url(settings.searxng_url),
            max_bytes=settings.max_lookup_response_bytes,
            params={"q": query, "format": "json", "language": "en", "categories": "general"},
            headers={"User-Agent": f"OIHK-Basic/{PRODUCT_VERSION}"},
        )
        results = []
        for r in (data or {}).get("results", [])[:max_results]:
            results.append(
                {
                    "title": r.get("title", ""),
                    "url": r.get("url", ""),
                    "snippet": r.get("content", ""),
                    "source_name": r.get("engine", "searxng"),
                }
            )
        return results


async def _search_brave(query: str, max_results: int) -> list[dict]:
    """Search via Brave Search API."""
    import httpx

    settings = get_settings()
    async with httpx.AsyncClient(timeout=15.0) as client:
        data = await get_json_bounded(
            client,
            "https://api.search.brave.com/res/v1/web/search",
            max_bytes=settings.max_lookup_response_bytes,
            params={"q": query, "count": max_results},
            headers={
                "Accept": "application/json",
                "X-Subscription-Token": settings.brave_api_key,
            },
        )
        results = []
        for r in (data or {}).get("web", {}).get("results", [])[:max_results]:
            results.append(
                {
                    "title": r.get("title", ""),
                    "url": r.get("url", ""),
                    "snippet": r.get("description", ""),
                    "source_name": "brave",
                }
            )
        return results
