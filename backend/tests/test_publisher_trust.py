"""Unit tests for the OIHK first-party publisher trust verification."""

from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path

import pytest
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
from cryptography.hazmat.primitives.serialization import Encoding, PublicFormat

from app.system_link import publisher_trust
from app.system_link.package_verification import calculate_package_sha256
from app.system_link.protocol import ModuleManifest, canonical_json
from app.system_link.publisher_trust import TrustAnchor, verify_publisher_trust
from app.system_link.security import b64decode, b64encode


def _public_key(key: Ed25519PrivateKey) -> str:
    return b64encode(key.public_key().public_bytes(Encoding.Raw, PublicFormat.Raw))


def _write_publisher_metadata(
    package_root: Path,
    *,
    module_id: str,
    version: str,
    key: Ed25519PrivateKey,
    channel: str,
) -> dict:
    metadata_dir = package_root / "metadata"
    metadata_dir.mkdir(exist_ok=True)
    content_hash = calculate_package_sha256(package_root, extra_ignored=frozenset({"metadata/publisher.json"}))
    publisher_public_key = _public_key(key)
    payload = {
        "algorithm": "Ed25519",
        "channel": channel,
        "content_sha256": content_hash,
        "module_id": module_id,
        "publisher": "OIHK",
        "publisher_fingerprint": hashlib.sha256(b64decode(publisher_public_key)).hexdigest(),
        "publisher_public_key": publisher_public_key,
        "version": version,
    }
    payload["signature"] = b64encode(key.sign(canonical_json(payload)))
    (metadata_dir / "publisher.json").write_text(json.dumps(payload, sort_keys=True) + "\n", encoding="utf-8")
    return payload


def _build_package(
    tmp_path: Path,
    *,
    channel: str = "development",
    key: Ed25519PrivateKey | None = None,
) -> tuple[Path, ModuleManifest, Ed25519PrivateKey]:
    package_root = tmp_path / "module-package"
    package_root.mkdir(parents=True)
    (package_root / "ui").mkdir()
    (package_root / "ui" / "index.js").write_text("export const module = 'evidence-lab';", encoding="utf-8")
    key = key or Ed25519PrivateKey.generate()
    _write_publisher_metadata(
        package_root, module_id="oihk.evidence-lab", version="0.1.0", key=key, channel=channel
    )
    executable_name = "evidence-lab-runtime.exe" if os.name == "nt" else "evidence-lab-runtime"
    manifest = ModuleManifest(
        module_id="oihk.evidence-lab",
        name="OIHK Evidence Lab Basic",
        version="0.1.0",
        compatible_basic_versions=["0.1.1-alpha.2"],
        requested_capabilities=["case.read", "ui.navigation.register"],
        package_sha256=calculate_package_sha256(package_root),
        frontend_entrypoint="ui/index.js",
        lifecycle={
            "entrypoint_id": "evidence-lab-runtime",
            "install_root": str(package_root.parent.resolve()),
            "executable": executable_name,
            "executable_sha256": "0" * 64,
            "base_url": "http://127.0.0.1:43119",
        },
    )
    return package_root, manifest, key


def _release_anchors(key: Ed25519PrivateKey) -> tuple[TrustAnchor, ...]:
    return (
        TrustAnchor(
            key_id="oihk-evidence-lab-publisher-test-2026",
            public_key=_public_key(key),
            channel="release",
            note="test anchor",
        ),
    )


def test_development_package_is_accepted_only_when_explicitly_enabled(tmp_path: Path) -> None:
    package_root, manifest, _ = _build_package(tmp_path, channel="development")
    result = verify_publisher_trust(package_root, manifest, allow_development=True)
    assert result["channel"] == "development"
    assert result["key_id"] == "development"

    with pytest.raises(publisher_trust.PublisherTrustError, match="not accepted"):
        verify_publisher_trust(package_root, manifest, allow_development=False)


def test_release_package_is_pinned_to_embedded_trust_anchors(tmp_path: Path, monkeypatch) -> None:
    key = Ed25519PrivateKey.generate()
    monkeypatch.setattr(publisher_trust, "RELEASE_TRUST_ANCHORS", _release_anchors(key))
    package_root, manifest, _ = _build_package(tmp_path, channel="release", key=key)
    result = verify_publisher_trust(package_root, manifest, allow_development=False)
    assert result["channel"] == "release"
    assert result["key_id"] == "oihk-evidence-lab-publisher-test-2026"


def test_unknown_release_publisher_is_rejected_fail_closed(tmp_path: Path, monkeypatch) -> None:
    # The package is signed by a key that is NOT in the embedded anchors.
    key = Ed25519PrivateKey.generate()
    monkeypatch.setattr(publisher_trust, "RELEASE_TRUST_ANCHORS", _release_anchors(Ed25519PrivateKey.generate()))
    package_root, manifest, _ = _build_package(tmp_path, channel="release", key=key)
    with pytest.raises(publisher_trust.PublisherTrustError, match="not in the OIHK first-party"):
        verify_publisher_trust(package_root, manifest, allow_development=False)


def test_altered_package_content_is_rejected(tmp_path: Path) -> None:
    package_root, manifest, _ = _build_package(tmp_path, channel="development")
    (package_root / "ui" / "index.js").write_text("tampered", encoding="utf-8")
    with pytest.raises(publisher_trust.PublisherTrustError, match="content does not match"):
        verify_publisher_trust(package_root, manifest, allow_development=True)


def test_invalid_publisher_signature_is_rejected(tmp_path: Path) -> None:
    package_root, manifest, _ = _build_package(tmp_path, channel="development")
    metadata = package_root / "metadata" / "publisher.json"
    payload = json.loads(metadata.read_text(encoding="utf-8"))
    payload["signature"] = b64encode(Ed25519PrivateKey.generate().sign(b"forged"))
    metadata.write_text(json.dumps(payload), encoding="utf-8")
    with pytest.raises(publisher_trust.PublisherTrustError, match="signature is invalid"):
        verify_publisher_trust(package_root, manifest, allow_development=True)


def test_unknown_channel_is_rejected(tmp_path: Path) -> None:
    package_root, manifest, _ = _build_package(tmp_path, channel="nightly")
    with pytest.raises(publisher_trust.PublisherTrustError, match="Unknown publisher channel"):
        verify_publisher_trust(package_root, manifest, allow_development=True)


def test_manifest_publisher_mismatch_is_rejected(tmp_path: Path) -> None:
    package_root, manifest, _ = _build_package(tmp_path, channel="development")
    manifest.version = "9.9.9"
    with pytest.raises(publisher_trust.PublisherTrustError, match="version does not match"):
        verify_publisher_trust(package_root, manifest, allow_development=True)


def test_unsafe_publisher_metadata_is_rejected(tmp_path: Path) -> None:
    package_root, manifest, _ = _build_package(tmp_path, channel="development")
    # Replace the metadata directory with a regular file: the verifier must
    # refuse to read publisher.json through a non-directory component.
    import shutil

    shutil.rmtree(package_root / "metadata")
    (package_root / "metadata").write_bytes(b"not-a-directory")
    with pytest.raises(publisher_trust.PublisherTrustError, match="missing, unsafe"):
        verify_publisher_trust(package_root, manifest, allow_development=True)


def test_malformed_publisher_metadata_is_rejected(tmp_path: Path) -> None:
    package_root, manifest, _ = _build_package(tmp_path, channel="development")
    (package_root / "metadata" / "publisher.json").write_text("{not-json", encoding="utf-8")
    with pytest.raises(publisher_trust.PublisherTrustError, match="malformed"):
        verify_publisher_trust(package_root, manifest, allow_development=True)


def test_key_rotation_keeps_old_and_new_release_keys_valid(tmp_path: Path, monkeypatch) -> None:
    old_key = Ed25519PrivateKey.generate()
    new_key = Ed25519PrivateKey.generate()
    anchors = (
        TrustAnchor(key_id="old-anchor", public_key=_public_key(old_key), channel="release"),
        TrustAnchor(key_id="new-anchor", public_key=_public_key(new_key), channel="release"),
    )
    monkeypatch.setattr(publisher_trust, "RELEASE_TRUST_ANCHORS", anchors)

    old_package, old_manifest, _ = _build_package(tmp_path / "old", channel="release", key=old_key)
    new_package, new_manifest, _ = _build_package(tmp_path / "new", channel="release", key=new_key)
    assert verify_publisher_trust(old_package, old_manifest, allow_development=False)["key_id"] == "old-anchor"
    assert verify_publisher_trust(new_package, new_manifest, allow_development=False)["key_id"] == "new-anchor"

    # After the old anchor is retired, old packages fail closed instead of degrading silently.
    monkeypatch.setattr(
        publisher_trust, "RELEASE_TRUST_ANCHORS", (anchors[1],)
    )
    with pytest.raises(publisher_trust.PublisherTrustError, match="not in the OIHK first-party"):
        verify_publisher_trust(old_package, old_manifest, allow_development=False)
    assert verify_publisher_trust(new_package, new_manifest, allow_development=False)["key_id"] == "new-anchor"
