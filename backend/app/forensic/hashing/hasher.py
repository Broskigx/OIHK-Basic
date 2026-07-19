"""File hashing utilities for OIHK Basic."""

import hashlib


def compute_hashes(data: bytes) -> dict[str, str]:
    """Compute MD5, SHA-1, and SHA-256 hashes of data."""
    return {
        "md5": hashlib.md5(data).hexdigest(),
        "sha1": hashlib.sha1(data).hexdigest(),
        "sha256": hashlib.sha256(data).hexdigest(),
    }
