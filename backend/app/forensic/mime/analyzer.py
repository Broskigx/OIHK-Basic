"""MIME type detection for OIHK Basic.

Most formats announce themselves with a fixed prefix and are matched from the
table below. Two families do not, and both were previously mis-reported:

* **RIFF** is a *container*. ``RIFF`` names the wrapper, not the content — the
  form type at offset 8 does. Matching the wrapper alone labelled every WAV
  recording and every WebP image in an exhibit as ``video/avi``.
* **ISO base media** (MP4 and its relatives) puts ``ftyp`` at offset 4, behind a
  box length that varies by encoder. Folding that length into a fixed prefix
  recognised exactly one encoder's output and let the rest fall through to
  ``application/octet-stream``.

Both are resolved by reading the field that actually carries the answer, which
is why they are handled ahead of the prefix table rather than inside it.
"""

_MAGIC_BYTES: dict[bytes, tuple[str, str, str]] = {
    b"\x89PNG\r\n\x1a\n": ("image/png", "png", "PNG image"),
    b"\xff\xd8\xff": ("image/jpeg", "jpeg", "JPEG image"),
    b"GIF87a": ("image/gif", "gif", "GIF image"),
    b"GIF89a": ("image/gif", "gif", "GIF image"),
    b"BM": ("image/bmp", "bmp", "BMP image"),
    b"%PDF": ("application/pdf", "pdf", "PDF document"),
    b"PK\x03\x04": ("application/zip", "zip", "ZIP archive"),
    b"\x1f\x8b\x08": ("application/gzip", "gzip", "GZip archive"),
    b"\x42\x5a\x68": ("application/x-bzip2", "bzip2", "BZip2 archive"),
    b"\xfd7zXZ\x00": ("application/x-xz", "xz", "XZ archive"),
    b"7z\xbc\xaf\x27\x1c": ("application/x-7z-compressed", "7z", "7-Zip archive"),
    b"Rar!\x1a\x07": ("application/vnd.rar", "rar", "RAR archive"),
    b"\x25\x21": ("application/postscript", "ps", "PostScript"),
    b"\x7fELF": ("application/x-elf", "elf", "ELF binary"),
    b"\x4d\x5a": ("application/x-dosexec", "pe", "PE executable"),
    b"\xca\xfe\xba\xbe": ("application/java-vm", "class", "Java class"),
    b"\x1a\x45\xdf\xa3": ("video/webm", "webm", "WebM video"),
    b"\x49\x44\x33": ("audio/mpeg", "mp3", "MP3 audio"),
    b"\xff\xfb": ("audio/mpeg", "mp3", "MP3 audio"),
    b"OggS": ("audio/ogg", "ogg", "Ogg container"),
    b"fLaC": ("audio/flac", "flac", "FLAC audio"),
    b"SQLite format 3\x00": ("application/vnd.sqlite3", "sqlite", "SQLite database"),
}

# Form type at offset 8 of a RIFF file.
_RIFF_FORMS: dict[bytes, tuple[str, str, str]] = {
    b"AVI ": ("video/avi", "avi", "AVI video"),
    b"WAVE": ("audio/wav", "wav", "WAV audio"),
    b"WEBP": ("image/webp", "webp", "WebP image"),
}

# Major brand at offset 8 of an ISO base media file. Brands outside this table
# are still ISO base media, so they resolve to the MP4 default rather than to
# "unknown" — see ``_detect_iso_base_media``.
_FTYP_BRANDS: dict[bytes, tuple[str, str, str]] = {
    b"qt  ": ("video/quicktime", "mov", "QuickTime video"),
    b"M4A ": ("audio/mp4", "m4a", "MPEG-4 audio"),
    b"M4B ": ("audio/mp4", "m4a", "MPEG-4 audio"),
    b"heic": ("image/heic", "heic", "HEIC image"),
    b"heix": ("image/heic", "heic", "HEIC image"),
    b"mif1": ("image/heif", "heif", "HEIF image"),
    b"avif": ("image/avif", "avif", "AVIF image"),
}
_ISO_BASE_MEDIA_DEFAULT = ("video/mp4", "mp4", "MP4 video")

_EXTENSION_TYPES: dict[str, tuple[str, str, str]] = {
    "html": ("text/html", "html", "HTML document"),
    "htm": ("text/html", "html", "HTML document"),
    "json": ("application/json", "json", "JSON data"),
    "csv": ("text/csv", "csv", "CSV spreadsheet"),
    "txt": ("text/plain", "text", "Plain text"),
    "xml": ("application/xml", "xml", "XML document"),
    "docx": ("application/vnd.openxmlformats-officedocument", "ooxml", "Office Open XML"),
    "xlsx": ("application/vnd.openxmlformats-officedocument", "ooxml", "Office Open XML"),
    "pptx": ("application/vnd.openxmlformats-officedocument", "ooxml", "Office Open XML"),
    "doc": ("application/msword", "ole2", "OLE2 document"),
    "xls": ("application/msword", "ole2", "OLE2 document"),
    "ppt": ("application/msword", "ole2", "OLE2 document"),
}


def _detect_riff(data: bytes) -> tuple[str, str, str] | None:
    """Resolve a RIFF wrapper to the format its form type names."""
    if not data.startswith(b"RIFF") or len(data) < 12:
        return None
    # An unrecognised form type is still a RIFF file, and saying so is more
    # honest than naming a specific format the bytes do not support.
    return _RIFF_FORMS.get(data[8:12], ("application/x-riff", "riff", "RIFF container"))


def _detect_iso_base_media(data: bytes) -> tuple[str, str, str] | None:
    """Resolve an ``ftyp`` box to its major brand, whatever the box length."""
    if len(data) < 12 or data[4:8] != b"ftyp":
        return None
    return _FTYP_BRANDS.get(data[8:12], _ISO_BASE_MEDIA_DEFAULT)


def detect_mime_type(data: bytes, content_type: str, extension: str) -> tuple[str, str, str]:
    """Detect MIME type from the file's own bytes, falling back to its extension.

    Returns ``(mime_type, detected_type, human_label)``. The declared
    ``content_type`` is consulted last: it comes from the uploader, so a file
    whose bytes identify it is never overruled by what it claimed to be.
    """
    for container in (_detect_riff(data), _detect_iso_base_media(data)):
        if container is not None:
            return container

    for magic, identity in _MAGIC_BYTES.items():
        if data.startswith(magic):
            return identity

    if (by_extension := _EXTENSION_TYPES.get(extension.lower().lstrip("."))) is not None:
        return by_extension

    return content_type or "application/octet-stream", "unknown", "Unknown"
