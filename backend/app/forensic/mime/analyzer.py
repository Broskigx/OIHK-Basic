"""MIME type detection for OIHK Basic."""

_MAGIC_BYTES: dict[str, tuple[str, str, str]] = {
    b"\x89PNG\r\n\x1a\n": ("image/png", "png", "PNG image"),
    b"\xff\xd8\xff": ("image/jpeg", "jpeg", "JPEG image"),
    b"GIF87a": ("image/gif", "gif", "GIF image"),
    b"GIF89a": ("image/gif", "gif", "GIF image"),
    b"%PDF": ("application/pdf", "pdf", "PDF document"),
    b"PK\x03\x04": ("application/zip", "zip", "ZIP archive"),
    b"\x1f\x8b\x08": ("application/gzip", "gzip", "GZip archive"),
    b"\x42\x5a\x68": ("application/x-bzip2", "bzip2", "BZip2 archive"),
    b"\x25\x21": ("application/postscript", "ps", "PostScript"),
    b"\x7fELF": ("application/x-elf", "elf", "ELF binary"),
    b"\x4d\x5a": ("application/x-dosexec", "pe", "PE executable"),
    b"\xca\xfe\xba\xbe": ("application/java-vm", "class", "Java class"),
    b"\x1a\x45\xdf\xa3": ("video/webm", "webm", "WebM video"),
    b"\x00\x00\x00\x18ftyp": ("video/mp4", "mp4", "MP4 video"),
    b"RIFF": ("video/avi", "avi", "AVI video"),
    b"\x49\x44\x33": ("audio/mpeg", "mp3", "MP3 audio"),
    b"\xff\xfb": ("audio/mpeg", "mp3", "MP3 audio"),
}


def detect_mime_type(data: bytes, content_type: str, extension: str) -> tuple[str, str, str]:
    """Detect MIME type from magic bytes."""
    for magic, (mime, dtype, label) in _MAGIC_BYTES.items():
        if data.startswith(magic):
            return mime, dtype, label

    if extension in ("html", "htm"):
        return "text/html", "html", "HTML document"
    if extension == "json":
        return "application/json", "json", "JSON data"
    if extension == "csv":
        return "text/csv", "csv", "CSV spreadsheet"
    if extension == "txt":
        return "text/plain", "text", "Plain text"
    if extension == "xml":
        return "application/xml", "xml", "XML document"
    if extension in ("docx", "xlsx", "pptx"):
        return "application/vnd.openxmlformats-officedocument", "ooxml", "Office Open XML"
    if extension in ("doc", "xls", "ppt"):
        return "application/msword", "ole2", "OLE2 document"

    return content_type or "application/octet-stream", "unknown", "Unknown"
