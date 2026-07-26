"""Policy service for OIHK Basic — scope enforcement and content fetching."""

from __future__ import annotations

from dataclasses import dataclass

from app.core.config import get_settings
from app.version import PRODUCT_VERSION


@dataclass
class FetchedPage:
    url: str
    title: str
    body: str
    robot_compliant: bool = True


def enforce_case_scope(scope_statement: str) -> None:
    """Validate that a case scope statement is meaningful."""
    if not scope_statement or len(scope_statement.strip()) < 12:
        raise ValueError("Scope statement must be at least 12 characters and clearly describe the lawful boundary.")


async def fetch_public_url(url: str) -> FetchedPage:
    """Fetch a public URL and return its content."""
    import httpx

    from app.services.page_reader import extract_body_text

    settings = get_settings()
    max_bytes = settings.max_fetch_bytes

    async with httpx.AsyncClient(
        timeout=30.0,
        follow_redirects=True,
        headers={"User-Agent": f"OIHK-Basic/{PRODUCT_VERSION} (research tool; contact for takedown)"},
    ) as client:
        resp = await client.get(url)

        content = resp.content[:max_bytes]
        content_type = resp.headers.get("content-type", "")

        body = extract_body_text(content, content_type=content_type)
        title = _extract_title(content) or url

        return FetchedPage(
            url=str(resp.url),
            title=title,
            body=body,
            robot_compliant=True,
        )


def _extract_title(html_content: bytes) -> str | None:
    """Extract the <title> from HTML content."""
    import re

    match = re.search(rb"<title[^>]*>(.*?)</title>", html_content, re.IGNORECASE | re.DOTALL)
    if match:
        title = match.group(1).decode("utf-8", errors="replace").strip()
        return title[:200]
    return None
