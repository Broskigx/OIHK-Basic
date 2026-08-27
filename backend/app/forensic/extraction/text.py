"""Text extraction for OIHK Basic."""

import re

from app.forensic.types import TextExtraction

_MAX_OOXML_MEMBER_BYTES = 10 * 1024 * 1024
# A presentation contributes one member per slide, so the member list is
# attacker-influenced in a way the fixed Word and Excel paths never were. The
# per-member byte ceiling bounds each read; this bounds how many of them run.
_MAX_OOXML_MEMBERS = 512


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


def _ooxml_members(archive) -> list[str]:
    """Return the text-bearing members of an OOXML package, in reading order.

    Word and Excel keep their text at one fixed path each. PowerPoint does not:
    its text lives in ``ppt/slides/slideN.xml``, one member per slide, with
    speaker notes alongside in ``ppt/notesSlides/``. Naming only the two fixed
    paths meant every ``.pptx`` was accepted, opened, and reported as holding no
    text at all — with an empty error list, so nothing distinguished a deck that
    could not be read from a deck with nothing in it.
    """
    names = set(archive.namelist())
    members = [name for name in ("word/document.xml", "xl/sharedStrings.xml") if name in names]

    def slide_order(name: str) -> tuple[int, str]:
        # slide10 must sort after slide2, which a plain string sort gets wrong.
        digits = re.findall(r"\d+", name.rsplit("/", 1)[-1])
        return (int(digits[-1]) if digits else 0, name)

    for prefix in ("ppt/slides/slide", "ppt/notesSlides/notesSlide"):
        members.extend(
            sorted(
                (name for name in names if name.startswith(prefix) and name.endswith(".xml")),
                key=slide_order,
            )
        )
    return members[:_MAX_OOXML_MEMBERS]


def _extract_ooxml(data: bytes, errors: list[str]) -> str:
    try:
        import io
        import zipfile

        texts: list[str] = []
        with zipfile.ZipFile(io.BytesIO(data)) as z:
            for member_name in _ooxml_members(z):
                try:
                    member = z.getinfo(member_name)
                except KeyError:
                    continue
                if member.file_size > _MAX_OOXML_MEMBER_BYTES:
                    errors.append(
                        f"OOXML member {member_name} exceeds the {_MAX_OOXML_MEMBER_BYTES}-byte extraction limit"
                    )
                    continue
                with z.open(member) as stream:
                    xml = stream.read(_MAX_OOXML_MEMBER_BYTES + 1)
                if len(xml) > _MAX_OOXML_MEMBER_BYTES:
                    errors.append(
                        f"OOXML member {member_name} exceeds the {_MAX_OOXML_MEMBER_BYTES}-byte extraction limit"
                    )
                    continue
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
