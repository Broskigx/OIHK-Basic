"""
Tests for first-run security: secret generation, persistence, and reusability.
"""

import io
import json
import os
import secrets
import stat
import sys
import tempfile
from pathlib import Path

import pytest

_HERE = Path(__file__).resolve().parent
_BASIC_ROOT = _HERE.parent


@pytest.fixture
def isolated_first_run(monkeypatch):
    """Set up a clean, isolated first_run module with a temp config directory."""
    with tempfile.TemporaryDirectory() as tmpdir:
        config_dir = Path(tmpdir) / "OIHK-Basic" / "config"
        config_dir.mkdir(parents=True, exist_ok=True)

        # Force-reload first_run with a patched config dir
        import app.core.first_run as fr

        monkeypatch.setattr(fr, "_CONFIG_DIR", config_dir)
        monkeypatch.setattr(fr, "_SECRETS_FILE", config_dir / "secrets.json")

        yield fr  # yield the module reference for tests to use


class TestSecretGeneration:

    def test_generates_on_first_call(self, isolated_first_run):
        fr = isolated_first_run
        secret = fr.get_or_create_secret("test_gen", 32)
        assert len(secret) > 20
        assert isinstance(secret, str)

    def test_persists_between_calls(self, isolated_first_run):
        fr = isolated_first_run
        original = fr.get_or_create_secret("persist_test", 32)
        reloaded = fr.get_or_create_secret("persist_test", 32)
        assert original == reloaded

    def test_different_keys_different_secrets(self, isolated_first_run):
        fr = isolated_first_run
        jwt = fr.get_or_create_secret("jwt_secret", 32)
        custody = fr.get_or_create_secret("custody_signing_key", 32)
        assert jwt != custody

    def test_secret_not_in_stdout(self, isolated_first_run):
        fr = isolated_first_run
        captured = io.StringIO()
        old_stdout = sys.stdout
        sys.stdout = captured
        try:
            secret = fr.get_or_create_secret("quiet_test", 32)
            output = captured.getvalue()
            assert secret not in output, "Secret should not appear in stdout"
        finally:
            sys.stdout = old_stdout

    def test_secrets_file_created_in_correct_location(self, isolated_first_run):
        fr = isolated_first_run
        fr.get_or_create_secret("loc_test", 32)
        assert fr._SECRETS_FILE.exists(), "Secrets file should exist"
        content = json.loads(fr._SECRETS_FILE.read_text(encoding="utf-8"))
        assert "loc_test" in content, "Secret should be in the file"

    def test_jwt_secret_function(self, isolated_first_run):
        fr = isolated_first_run
        jwt = fr.get_jwt_secret()
        assert len(jwt) > 20

    def test_custody_secret_function(self, isolated_first_run):
        fr = isolated_first_run
        custody = fr.get_custody_signing_key()
        assert len(custody) > 20

    def test_secrets_exist_returns_true_after_creation(self, isolated_first_run):
        fr = isolated_first_run
        assert not fr.secrets_exist()
        fr.get_jwt_secret()
        fr.get_custody_signing_key()
        assert fr.secrets_exist()

    def test_secrets_file_is_outside_repo(self, isolated_first_run):
        """Verify secrets are stored outside the project directory."""
        fr = isolated_first_run
        fr.get_or_create_secret("loc_test", 32)
        secrets_path = fr._SECRETS_FILE.resolve()
        assert _BASIC_ROOT not in secrets_path.parents, \
            f"Secrets file {secrets_path} must be outside the repo"

    def test_no_change_me_placeholders_in_config(self):
        """Verify no 'change-me' placeholder secrets exist in config files."""
        danger_patterns = [
            "change-me-in-production-oihk-basic-secret",
            "change-me-in-production-oihk-basic-custody-secret",
        ]
        search_dirs = [
            _BASIC_ROOT / "backend" / "app" / "core",
            _BASIC_ROOT,
        ]
        for search_dir in search_dirs:
            if not search_dir.is_dir():
                continue
            for filepath in search_dir.rglob("*.py"):
                # Skip test files (they may reference patterns as test data)
                if "test_" in filepath.name:
                    continue
                try:
                    content = filepath.read_text(encoding="utf-8", errors="ignore")
                except (OSError, PermissionError):
                    continue
                for pattern in danger_patterns:
                    if pattern in content:
                        pytest.fail(f"Found placeholder '{pattern}' in {filepath}")
            for filepath in search_dir.glob(".env*"):
                if not filepath.is_file():
                    continue
                try:
                    content = filepath.read_text(encoding="utf-8", errors="ignore")
                except (OSError, PermissionError):
                    continue
                for pattern in danger_patterns:
                    if pattern in content:
                        pytest.fail(f"Found placeholder '{pattern}' in {filepath}")

    @pytest.mark.skipif(os.name == "nt", reason="umask-based permissions not enforceable on Windows")
    def test_secrets_file_restricted_permissions_unix(self, isolated_first_run):
        """On Unix: verify secrets file permissions are restricted (0o600 or stricter)."""
        fr = isolated_first_run
        fr.get_or_create_secret("perm_test", 32)
        file_stat = fr._SECRETS_FILE.stat()
        # Check that group/other have no read/write
        mode = file_stat.st_mode
        # 0o077 masks out group/other permissions
        assert (mode & stat.S_IRWXO) == 0, "Other users should not have access"
        assert (mode & stat.S_IRWXG) == 0, "Group should not have access"
