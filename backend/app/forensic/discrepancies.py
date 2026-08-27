"""Content-versus-name discrepancy detection.

An exhibit's name is a claim; its bytes are the evidence. Where the two
disagree, that disagreement is itself a finding — a PE executable carrying a
``.jpg`` extension is the single most common masquerade an analyst looks for,
and it is invisible in a report that only lists what the file says it is.

The rules here are deliberately narrow. A detector that fires on ordinary
exhibits trains its reader to skip the panel, so every rule below either
compares two *positive* identifications or says nothing: whenever the content
cannot be identified from its own bytes, no rule fires, because "unrecognised"
is not evidence of a mismatch.
"""

from __future__ import annotations

from pathlib import PurePosixPath

# Detected types that mean "this file is code that runs".
_EXECUTABLE_TYPES = frozenset({"pe", "elf", "class"})

_EXECUTABLE_EXTENSIONS = frozenset(
    {
        "exe", "dll", "sys", "scr", "com", "msi", "cpl", "ocx",
        "so", "dylib", "bin", "class", "jar",
        "bat", "cmd", "ps1", "psm1", "sh", "vbs", "vbe", "js", "jse", "wsf", "hta", "lnk",
    }
)

# Extensions a reader would assume are inert content. An executable outer
# extension behind one of these is the classic "invoice.pdf.exe" dressing.
_INERT_EXTENSIONS = frozenset(
    {
        "pdf", "doc", "docx", "xls", "xlsx", "ppt", "pptx", "rtf", "odt", "ods",
        "txt", "csv", "xml", "json", "html", "htm", "log", "md",
        "jpg", "jpeg", "png", "gif", "bmp", "webp", "heic", "svg", "tif", "tiff",
        "mp3", "wav", "mp4", "mov", "avi", "webm", "zip", "rar", "7z",
    }
)

# What each extension's bytes should identify as. An extension absent from this
# map carries no expectation, so it produces no finding.
_EXPECTED_BY_EXTENSION: dict[str, frozenset[str]] = {
    "png": frozenset({"png"}),
    "jpg": frozenset({"jpeg"}),
    "jpeg": frozenset({"jpeg"}),
    "gif": frozenset({"gif"}),
    "bmp": frozenset({"bmp"}),
    "webp": frozenset({"webp"}),
    "heic": frozenset({"heic", "heif"}),
    "avif": frozenset({"avif"}),
    "pdf": frozenset({"pdf"}),
    "zip": frozenset({"zip"}),
    # OOXML packages are ZIP archives, so their bytes legitimately identify as
    # either. Demanding "ooxml" here would flag every genuine Office document.
    "docx": frozenset({"zip", "ooxml"}),
    "xlsx": frozenset({"zip", "ooxml"}),
    "pptx": frozenset({"zip", "ooxml"}),
    "gz": frozenset({"gzip"}),
    "bz2": frozenset({"bzip2"}),
    "xz": frozenset({"xz"}),
    "7z": frozenset({"7z"}),
    "rar": frozenset({"rar"}),
    "exe": frozenset({"pe"}),
    "dll": frozenset({"pe"}),
    "sys": frozenset({"pe"}),
    "so": frozenset({"elf"}),
    "class": frozenset({"class"}),
    "mp4": frozenset({"mp4"}),
    "m4v": frozenset({"mp4"}),
    "m4a": frozenset({"m4a", "mp4"}),
    "mov": frozenset({"mov", "mp4"}),
    "avi": frozenset({"avi"}),
    "wav": frozenset({"wav"}),
    "webm": frozenset({"webm"}),
    "mp3": frozenset({"mp3"}),
    "ogg": frozenset({"ogg"}),
    "flac": frozenset({"flac"}),
    "sqlite": frozenset({"sqlite"}),
    "db": frozenset({"sqlite"}),
}

# Types the uploader sends when it does not know, which contradict nothing.
_GENERIC_CONTENT_TYPES = frozenset(
    {"", "application/octet-stream", "binary/octet-stream", "application/unknown", "*/*"}
)


def _normalize_content_type(value: str) -> str:
    return value.split(";", 1)[0].strip().lower()


def _extensions(filename: str) -> list[str]:
    """Return every dotted suffix of ``filename``, outermost last."""
    return [part.lower() for part in PurePosixPath(filename).suffixes]


def detect_discrepancies(
    *,
    filename: str,
    extension: str,
    detected_type: str,
    mime_type: str,
    declared_content_type: str,
) -> list[str]:
    """Report where a file's name or declared type contradicts its own bytes.

    ``detected_type`` and ``mime_type`` come from
    :func:`app.forensic.mime.analyzer.detect_mime_type`, which reads the file's
    magic bytes. ``extension`` and ``declared_content_type`` come from whoever
    supplied the file, and are therefore the claims being tested.
    """
    findings: list[str] = []
    extension = extension.lower().lstrip(".")
    detected_type = detected_type.lower()
    identified = detected_type != "unknown"

    # 1. Executable content behind a name that does not announce it. Listed
    #    first and separately from the generic mismatch below because it is the
    #    finding an analyst most needs to see, and it holds even when the
    #    extension carries no specific expectation.
    if identified and detected_type in _EXECUTABLE_TYPES and extension not in _EXECUTABLE_EXTENSIONS:
        findings.append(
            f"Executable content: the bytes identify as {mime_type}, but the "
            f"{f'.{extension}' if extension else 'missing'} extension does not announce an executable."
        )

    # 2. The extension states a format the bytes contradict.
    expected = _EXPECTED_BY_EXTENSION.get(extension)
    if identified and expected is not None and detected_type not in expected:
        findings.append(
            f"Extension mismatch: .{extension} implies {'/'.join(sorted(expected))}, "
            f"but the content identifies as {detected_type} ({mime_type})."
        )

    # 3. The uploader's declared media type contradicts the bytes. Skipped for
    #    the generic types, which assert nothing to contradict.
    declared = _normalize_content_type(declared_content_type)
    if identified and declared not in _GENERIC_CONTENT_TYPES and declared != _normalize_content_type(mime_type):
        findings.append(
            f"Declared type mismatch: the upload declared {declared}, but the content identifies as {mime_type}."
        )

    # 4. A double extension whose outer half runs and whose inner half reads as
    #    inert. This one tests the name alone, so it stands regardless of
    #    whether the bytes were identified.
    suffixes = _extensions(filename)
    if len(suffixes) >= 2:
        outer = suffixes[-1].lstrip(".")
        inner = suffixes[-2].lstrip(".")
        if outer in _EXECUTABLE_EXTENSIONS and inner in _INERT_EXTENSIONS:
            findings.append(
                f"Double extension: '{PurePosixPath(filename).name}' presents as .{inner} "
                f"but runs as .{outer}."
            )

    return findings
