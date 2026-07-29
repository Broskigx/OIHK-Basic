from __future__ import annotations

from app.core.config import get_settings


def test_packaged_desktop_ignores_working_directory_dotenv(tmp_path, monkeypatch) -> None:
    (tmp_path / ".env").write_text(
        "OIHK_AUTH_ENABLED=true\nOIHK_DATABASE_URL=sqlite+aiosqlite:///attacker.db\n",
        encoding="utf-8",
    )
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("OIHK_DESKTOP_PACKAGED", "1")
    monkeypatch.setenv("OIHK_AUTH_ENABLED", "true")
    monkeypatch.setenv("OIHK_DATABASE_URL", "sqlite+aiosqlite:///ambient-attacker.db")
    monkeypatch.setenv("OIHK_STORAGE_DIR", str(tmp_path / "ambient-storage"))
    monkeypatch.setenv("OIHK_CORS_ORIGINS", "*")
    get_settings.cache_clear()
    try:
        settings = get_settings()
        assert settings.auth_enabled is False
        assert "attacker.db" not in settings.database_url
        assert settings.storage_dir != str(tmp_path / "ambient-storage")
        assert "*" not in settings.cors_origin_list
        assert settings.cors_origin_list == ["http://tauri.localhost", "tauri://localhost"]
        assert settings.environment == "desktop"
    finally:
        get_settings.cache_clear()


def test_packaged_desktop_accepts_only_internal_managed_data_directory(tmp_path, monkeypatch) -> None:
    managed = tmp_path / "managed"
    monkeypatch.setenv("OIHK_DESKTOP_PACKAGED", "1")
    monkeypatch.setenv("OIHK_PACKAGED_DATA_DIR", str(managed))
    monkeypatch.setenv("OIHK_DATABASE_URL", "sqlite+aiosqlite:///ambient-attacker.db")
    get_settings.cache_clear()
    try:
        settings = get_settings()
        assert settings.database_url == f"sqlite+aiosqlite:///{(managed / 'oihk-basic.db').as_posix()}"
        assert settings.storage_dir == str(managed / "storage")
    finally:
        get_settings.cache_clear()
