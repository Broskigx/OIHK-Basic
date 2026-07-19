"""Text extraction for OIHK Basic."""

import re

from app.forensic.types import TextExtraction


def extract_text(data: bytes, filename: str, content_type: str) -> TextExtraction:
    """Extract text from file data based on type."""
    errors: list[str] = []
    text = ""

    content_lower = content_type.lower()
    ext = filename.rsplit(".", 1)[-1].lower() if "." in filename else ""

    if "html" in content_lower or ext in ("html", "htm"):
        text = _extract_html(data)
    elif "pdf" in content_lower or ext == "pdf":
        text = _extract_pdf(data, errors)
    elif ext in ("docx", "xlsx", "pptx"):
        text = _extract_ooxml(data, errors)
    elif ext == "json":
        text = _extract_json(data)
    elif "text" in content_lower or ext in ("txt", "csv", "xml", "yaml", "yml"):
        text = data.decode("utf-8", errors="replace")
    else:
        text = data.decode("utf-8", errors="replace")

    words = text.split()
    return TextExtraction(
        format=ext or content_lower.split("/")[-1],
        text=text,
        char_count=len(text),
        word_count=len(words),
        errors=errors,
    )


def _extract_html(data: bytes) -> str:
    text = data.decode("utf-8", errors="replace")
    text = re.sub(r"<script[^>]*>.*?</script>", "", text, flags=re.DOTALL | re.IGNORECASE)
    text = re.sub(r"<style[^>]*>.*?</style>", "", text, flags=re.DOTALL | re.IGNORECASE)
    text = re.sub(r"<[^>]+>", " ", text)
    text = re.sub(r"\s+", " ", text)
    return text.strip()


def _extract_pdf(data: bytes, errors: list[str]) -> str:
    try:
        text = data.decode("latin-1")
        # Simple PDF text extraction - find text between parentheses in PDF streams
        texts: list[str] = []
        for match in re.finditer(rb"\((.*?)\)", data):
            try:
                t = match.group(1).decode("latin-1")
                if len(t) > 3:
                    texts.append(t)
            except Exception:
                pass
        return " ".join(texts)
    except Exception as e:
        errors.append(f"PDF text extraction failed: {e}")
        return ""


def _extract_ooxml(data: bytes, errors: list[str]) -> str:
    try:
        import zipfile
        import io

        texts: list[str] = []
        with zipfile.ZipFile(io.BytesIO(data)) as z:
            if "word/document.xml" in z.namelist():
                xml = z.read("word/document.xml")
                # Simple XML tag stripping
                text = xml.decode("utf-8", errors="replace")
                text = re.sub(r"<[^>]+>", " ", text)
                text = re.sub(r"\s+", " ", text)
                texts.append(text)
            if "xl/sharedStrings.xml" in z.namelist():
                xml = z.read("xl/sharedStrings.xml")
                text = xml.decode("utf-8", errors="replace")
                text = re.sub(r"<[^>]+>", " ", text)
                text = re.sub(r"\s+", " ", text)
                texts.append(text)
        return " ".join(texts)
    except Exception as e:
        errors.append(f"OOXML extraction failed: {e}")
        return ""


def _extract_json(data: bytes) -> str:
    try:
        import json
        obj = json.loads(data)
        return json.dumps(obj, indent=2)
    except Exception:
        return data.decode("utf-8", errors="replace")
