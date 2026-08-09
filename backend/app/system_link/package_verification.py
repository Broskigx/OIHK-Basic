"""Deterministic verification for local, signed System Link UI packages."""

from __future__ import annotations

import hashlib
from pathlib import Path

_IGNORED_METADATA = frozenset({"manifest.json", "manifest.sig", "package.sha256"})


class PackageVerificationError(ValueError):
    pass


def calculate_package_sha256(root_value: str | Path) -> str:
    declared_root = Path(root_value)
    if declared_root.is_symlink():
        raise PackageVerificationError("Module package root may not be a symlink")
    root = declared_root.resolve(strict=True)
    if not root.is_dir():
        raise PackageVerificationError("Module package root must be a regular directory")
    files: list[tuple[str, Path]] = []
    total_bytes = 0
    for path in root.rglob("*"):
        if path.is_symlink():
            raise PackageVerificationError("Module packages may not contain symlinks")
        if not path.is_file():
            continue
        relative = path.relative_to(root).as_posix()
        if relative in _IGNORED_METADATA:
            continue
        if ".." in relative.split("/"):
            raise PackageVerificationError("Module package path traversal detected")
        total_bytes += path.stat().st_size
        if total_bytes > 256 * 1024 * 1024:
            raise PackageVerificationError("Module package exceeds the 256 MB host limit")
        files.append((relative, path))
    if not files:
        raise PackageVerificationError("Module package contains no verifiable content")
    if len(files) > 2048:
        raise PackageVerificationError("Module package contains too many files")
    digest = hashlib.sha256()
    for relative, path in sorted(files):
        content_digest = hashlib.sha256()
        with path.open("rb") as source:
            while chunk := source.read(1024 * 1024):
                content_digest.update(chunk)
        file_digest = content_digest.hexdigest()
        digest.update(relative.encode("utf-8"))
        digest.update(b"\x00")
        digest.update(file_digest.encode("ascii"))
        digest.update(b"\n")
    return digest.hexdigest()


def verify_package(root: str | Path, expected_sha256: str) -> str:
    actual = calculate_package_sha256(root)
    if actual != expected_sha256.lower():
        raise PackageVerificationError("Module package hash does not match its signed manifest")
    return actual


def verify_executable(descriptor) -> Path:
    executable = descriptor.resolve_executable()
    digest = hashlib.sha256()
    with executable.open("rb") as source:
        while chunk := source.read(1024 * 1024):
            digest.update(chunk)
    if digest.hexdigest() != descriptor.executable_sha256:
        raise PackageVerificationError("Registered runtime executable hash does not match")
    return executable
