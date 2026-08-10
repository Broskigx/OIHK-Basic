"""First-party publisher trust for OIHK System Link module packages.

OIHK Basic embeds a small, explicit and auditable set of OIHK publisher
trust anchors (Ed25519 public keys). A module package is accepted only when:

* ``metadata/publisher.json`` exists, is a regular non-symlink file, and
  matches the signed v1 publisher contract;
* the publisher-signed ``content_sha256`` matches the package on disk;
* the Ed25519 signature verifies under the declared publisher key;
* ``channel == "release"`` and the publisher key fingerprint is present in
  the embedded release trust anchors; or
* ``channel == "development"`` and the host explicitly enables development
  publishers through settings (development keys are ephemeral by design and
  therefore cannot be pinned in advance).

Every failure path is fail-closed. The release private key is never stored in
any repository; it lives in the OIHK Evidence Lab release secret store and is
referenced here only through its public half.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path

from app.system_link.package_verification import calculate_package_sha256
from app.system_link.protocol import ModuleManifest, canonical_json
from app.system_link.security import public_key_fingerprint, verify_signature

_REQUIRED_FIELDS = frozenset(
    {
        "algorithm",
        "channel",
        "content_sha256",
        "module_id",
        "publisher",
        "publisher_fingerprint",
        "publisher_public_key",
        "signature",
        "version",
    }
)

# The publisher signature covers every content file EXCEPT the publisher
# metadata itself (the package content hash is computed before the metadata is
# written, mirroring the Evidence Lab build pipeline).
_PUBLISHER_METADATA_PATHS = frozenset({"metadata/publisher.json"})


class PublisherTrustError(ValueError):
    pass


@dataclass(frozen=True)
class TrustAnchor:
    """One embedded OIHK first-party publisher key."""

    key_id: str
    public_key: str
    channel: str
    note: str = ""

    @property
    def fingerprint(self) -> str:
        return public_key_fingerprint(self.public_key)


# Rotation policy: add a new anchor before switching the Evidence Lab release
# pipeline to its successor key, keep both during a transition window, then
# remove the retired anchor. Old packages remain verifiable while their anchor
# is listed.
RELEASE_TRUST_ANCHORS: tuple[TrustAnchor, ...] = (
    TrustAnchor(
        key_id="oihk-evidence-lab-publisher-2026-08",
        public_key="XMNUmOlZFnyFpZyauCWUe3RBdsiIO-v2dcutinnpAWU",
        channel="release",
        note="OIHK Evidence Lab release publisher key generated 2026-08. "
        "The matching private key is held only in the Evidence Lab release secret store. "
        "Fingerprint 2efbb614d123f1257470ec425e1377fb698ad42c0d1098085db423d2b80d92ea.",
    ),
)


def _public_key_fingerprints(anchors: tuple[TrustAnchor, ...]) -> set[str]:
    return {anchor.fingerprint for anchor in anchors}


def verify_publisher_trust(
    package_root: str | Path,
    manifest: ModuleManifest,
    *,
    allow_development: bool,
) -> dict:
    """Verify the package publisher identity fail-closed and return its metadata.

    Raises :class:`PublisherTrustError` on any invalid, altered, unknown or
    unauthorized publisher state.
    """
    root = Path(package_root).resolve(strict=True)
    metadata_path = root / "metadata" / "publisher.json"
    if metadata_path.is_symlink() or not metadata_path.is_file() or metadata_path.stat().st_size > 16 * 1024:
        raise PublisherTrustError("Publisher metadata is missing, unsafe, or oversized")
    try:
        signed = json.loads(metadata_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise PublisherTrustError("Publisher metadata is malformed") from exc
    if not isinstance(signed, dict) or set(signed) != _REQUIRED_FIELDS:
        raise PublisherTrustError("Publisher metadata fields do not match the signed v1 contract")

    signature = str(signed.pop("signature"))
    if signed["algorithm"] != "Ed25519":
        raise PublisherTrustError("Publisher metadata algorithm is not Ed25519")
    if signed["module_id"] != manifest.module_id:
        raise PublisherTrustError("Publisher metadata module_id does not match the signed manifest")
    if signed["version"] != manifest.version:
        raise PublisherTrustError("Publisher metadata version does not match the signed manifest")
    try:
        if public_key_fingerprint(str(signed["publisher_public_key"])) != signed["publisher_fingerprint"]:
            raise PublisherTrustError("Publisher public key fingerprint does not match")
    except (ValueError, TypeError) as exc:
        raise PublisherTrustError("Publisher public key is malformed") from exc

    content_hash = calculate_package_sha256(root, extra_ignored=_PUBLISHER_METADATA_PATHS)
    if content_hash != signed["content_sha256"]:
        raise PublisherTrustError("Publisher-signed package content does not match the package on disk")

    try:
        verify_signature(str(signed["publisher_public_key"]), canonical_json(signed), signature)
    except Exception as exc:
        raise PublisherTrustError("Publisher metadata signature is invalid") from exc

    channel = str(signed["channel"])
    if channel == "release":
        release_fingerprints = _public_key_fingerprints(RELEASE_TRUST_ANCHORS)
        if signed["publisher_fingerprint"] not in release_fingerprints:
            raise PublisherTrustError("Publisher is not in the OIHK first-party release trust anchors")
        key_id = next(
            anchor.key_id for anchor in RELEASE_TRUST_ANCHORS if anchor.fingerprint == signed["publisher_fingerprint"]
        )
    elif channel == "development":
        if not allow_development:
            raise PublisherTrustError("Development publisher signatures are not accepted by this host configuration")
        key_id = "development"
    else:
        raise PublisherTrustError(f"Unknown publisher channel {channel!r}")

    return {**signed, "signature": signature, "key_id": key_id}
