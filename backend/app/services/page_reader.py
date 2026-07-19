"""Page reader for OIHK Basic — extract text from HTML/simple content."""

from __future__ import annotations

import re


def extract_body_text(content: bytes, content_type: str = "") -> str:
    """Extract readable text from page content."""
    if "html" in content_type.lower():
        return _extract_html_text(content)
    try:
        return content.decode("utf-8", errors="replace")
    except Exception:
        return content.decode("latin-1", errors="replace")


def _extract_html_text(html: bytes) -> str:
    """Extract text from HTML, removing scripts, styles, and tags."""
    text = html.decode("utf-8", errors="replace")

    # Remove scripts and styles
    text = re.sub(r"<script[^>]*>.*?</script>", "", text, flags=re.DOTALL | re.IGNORECASE)
    text = re.sub(r"<style[^>]*>.*?</style>", "", text, flags=re.DOTALL | re.IGNORECASE)
    text = re.sub(r"<[^>]+>", " ", text)
    text = re.sub(r"\s+", " ", text)
    text = re.sub(r"&[a-z]+;", " ", text)

    return text.strip()[:100_000]
