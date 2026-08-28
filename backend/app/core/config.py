"""OIHK Basic configuration — local-first, no cloud dependencies."""

import os
from functools import lru_cache
from pathlib import Path
from typing import Annotated

from pydantic import Field, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

from app.core.first_run import get_custody_key_id as _fr_custody_key_id
from app.core.first_run import get_custody_signing_key as _fr_custody
from app.core.first_run import get_jwt_secret as _fr_jwt

_DEFAULT_JWT_SECRET = _fr_jwt()
_DEFAULT_CUSTODY_SIGNING_KEY = _fr_custody()
_DEFAULT_CUSTODY_KEY_ID = _fr_custody_key_id()
_SQLITE_URL_PREFIXES = ("sqlite+aiosqlite:///", "sqlite:///")


def _normalize_sqlite_url(url: str) -> str:
    import re

    for prefix in _SQLITE_URL_PREFIXES:
        if not url.startswith(prefix):
            continue
        raw_path = url[len(prefix) :]
        if raw_path in {"", ":memory:"} or raw_path.startswith("/") or re.match(r"^[A-Za-z]:[/\\]", raw_path):
            return url
        db_path = (Path(__file__).resolve().parent.parent.parent / raw_path).resolve()
        return f"{prefix}{db_path.as_posix()}"
    return url


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
        populate_by_name=True,
    )

    # --- Application ---
    app_name: Annotated[str, Field(alias="OIHK_APP_NAME")] = "OIHK Basic"
    environment: Annotated[str, Field(alias="OIHK_ENVIRONMENT")] = "development"
    database_url: str = Field(default="", alias="OIHK_DATABASE_URL")
    cors_origins: Annotated[str, Field(alias="OIHK_CORS_ORIGINS")] = "http://127.0.0.1:5173,http://localhost:5173"
    api_log_level: str = "INFO"
    storage_dir: Annotated[str, Field(alias="OIHK_STORAGE_DIR")] = ""
    server_bind_host: Annotated[str, Field(alias="OIHK_SERVER_BIND_HOST")] = "127.0.0.1"
    # Host header allowlist. Empty means "derive from the bind address": a
    # loopback bind accepts only loopback authorities, which is what defeats DNS
    # rebinding. A non-loopback deployment sits behind a reverse proxy that
    # rewrites Host, so the operator must state the expected names explicitly.
    allowed_hosts: Annotated[str, Field(alias="OIHK_ALLOWED_HOSTS")] = ""
    # Interactive API docs are a discovery aid for an attacker who reaches the
    # loopback port. They stay on for development and are withdrawn from the
    # packaged desktop build, which never needs them.
    docs_enabled: Annotated[bool | None, Field(alias="OIHK_DOCS_ENABLED")] = None

    @property
    def effective_database_url(self) -> str:
        if self.database_url:
            return self.database_url
        return f"sqlite+aiosqlite:///{self._default_data_dir() / 'oihk-basic.db'}"

    @property
    def effective_storage_dir(self) -> str:
        if self.storage_dir:
            return self.storage_dir
        return str(self._default_data_dir() / "storage")

    @staticmethod
    def _default_data_dir() -> Path:
        import os as _os
        import platform as _platform

        system = _platform.system()
        if system == "Windows":
            base = _os.environ.get("APPDATA", _os.path.expanduser("~"))
            return Path(base) / "OIHK-Basic"
        elif system == "Darwin":
            return Path.home() / "Library" / "Application Support" / "OIHK-Basic"
        else:
            xdg = _os.environ.get("XDG_DATA_HOME", "")
            if xdg:
                return Path(xdg) / "OIHK-Basic"
            return Path.home() / ".local" / "share" / "OIHK-Basic"

    # --- AI (optional, local-only) ---
    ai_api_key: Annotated[str, Field(alias="OIHK_AI_API_KEY")] = ""
    ai_base_url: Annotated[str, Field(alias="OIHK_AI_BASE_URL")] = ""
    ai_model: Annotated[str, Field(alias="OIHK_AI_MODEL")] = ""
    ai_local: Annotated[bool, Field(alias="OIHK_AI_LOCAL")] = False
    ai_temperature: Annotated[float, Field(alias="OIHK_AI_TEMPERATURE")] = 0.2
    ai_max_tokens: Annotated[int, Field(alias="OIHK_AI_MAX_TOKENS")] = 2048
    ai_max_tool_steps: Annotated[int, Field(alias="OIHK_AI_MAX_TOOL_STEPS")] = 25

    # --- Web search (user-provided, no defaults) ---
    searxng_url: Annotated[str, Field(alias="OIHK_SEARXNG_URL")] = ""
    searxng_public_fallback: Annotated[bool, Field(alias="OIHK_SEARXNG_PUBLIC_FALLBACK")] = False
    brave_api_key: Annotated[str, Field(alias="OIHK_BRAVE_API_KEY")] = ""
    search_max_queries: Annotated[int, Field(alias="OIHK_SEARCH_MAX_QUERIES")] = 4
    search_max_results_per_query: Annotated[int, Field(alias="OIHK_SEARCH_MAX_RESULTS_PER_QUERY")] = 5
    search_target_results: Annotated[int, Field(alias="OIHK_SEARCH_TARGET_RESULTS")] = 50
    max_fetch_bytes: Annotated[int, Field(alias="OIHK_MAX_FETCH_BYTES")] = 1_048_576
    max_evidence_bytes: Annotated[int, Field(alias="OIHK_MAX_EVIDENCE_BYTES")] = 262_144_000
    # Deliberately far below max_evidence_bytes. A module call is authenticated
    # by a signature taken over the whole request body, so the host must buffer
    # every byte before it may trust any of them — the interactive upload path
    # streams to disk instead and can afford a much larger ceiling. Raising this
    # raises peak memory per in-flight module call, not just the file size.
    max_module_upload_bytes: Annotated[int, Field(alias="OIHK_MAX_MODULE_UPLOAD_BYTES")] = 33_554_432
    # Ceilings for third-party lookup and model responses. httpx decompresses
    # transparently, so an unbounded read lets a small compressed body expand
    # without limit in memory; these caps apply to the decompressed stream.
    max_lookup_response_bytes: Annotated[int, Field(alias="OIHK_MAX_LOOKUP_RESPONSE_BYTES")] = 5_242_880
    max_model_response_bytes: Annotated[int, Field(alias="OIHK_MAX_MODEL_RESPONSE_BYTES")] = 8_388_608
    max_model_stream_chars: Annotated[int, Field(alias="OIHK_MAX_MODEL_STREAM_CHARS")] = 1_000_000
    search_deep_read: Annotated[bool, Field(alias="OIHK_SEARCH_DEEP_READ")] = True
    search_max_pages: Annotated[int, Field(alias="OIHK_SEARCH_MAX_PAGES")] = 10
    search_link_depth: Annotated[int, Field(alias="OIHK_SEARCH_LINK_DEPTH")] = 1
    search_links_per_page: Annotated[int, Field(alias="OIHK_SEARCH_LINKS_PER_PAGE")] = 2

    # --- Authentication ---
    # The desktop edition is single-user and exposes its API only on loopback.
    # Authentication remains available as an explicit opt-in for custom deployments.
    auth_enabled: Annotated[bool, Field(alias="OIHK_AUTH_ENABLED")] = False
    jwt_secret: Annotated[str, Field(alias="OIHK_JWT_SECRET")] = _DEFAULT_JWT_SECRET
    custody_signing_key: Annotated[str, Field(alias="OIHK_CUSTODY_SIGNING_KEY")] = _DEFAULT_CUSTODY_SIGNING_KEY
    custody_key_id: Annotated[str, Field(alias="OIHK_CUSTODY_KEY_ID")] = _DEFAULT_CUSTODY_KEY_ID
    auto_create_tables: Annotated[bool | None, Field(alias="OIHK_AUTO_CREATE_TABLES")] = None
    jwt_algorithm: str = "HS256"
    access_token_ttl_minutes: Annotated[int, Field(alias="OIHK_ACCESS_TOKEN_TTL_MINUTES")] = 720
    bootstrap_admin_email: Annotated[str, Field(alias="OIHK_BOOTSTRAP_ADMIN_EMAIL")] = ""
    bootstrap_admin_password: Annotated[str, Field(alias="OIHK_BOOTSTRAP_ADMIN_PASSWORD")] = ""
    public_registration: Annotated[bool | None, Field(alias="OIHK_PUBLIC_REGISTRATION")] = None
    temporary_basic_login: Annotated[bool, Field(alias="OIHK_TEMPORARY_BASIC_LOGIN")] = False

    # --- System Link ---
    # Release packages are always pinned to the embedded first-party trust
    # anchors. Development publisher signatures are accepted ONLY when this
    # flag is explicitly enabled (development/CI/E2E). Production installs
    # must keep it off so unknown publisher keys are rejected fail-closed.
    system_link_allow_development_publishers: Annotated[bool, Field(alias="OIHK_SYSTEM_LINK_ALLOW_DEV_PUBLISHERS")] = (
        False
    )

    # --- Rate limiting ---
    rate_limit_enabled: Annotated[bool, Field(alias="OIHK_RATE_LIMIT_ENABLED")] = True
    rate_limit_per_minute: Annotated[int, Field(alias="OIHK_RATE_LIMIT_PER_MINUTE")] = 120
    rate_limit_trust_forwarded: Annotated[bool, Field(alias="OIHK_RATE_LIMIT_TRUST_FORWARDED")] = False
    trusted_proxy_ips: Annotated[str, Field(alias="OIHK_TRUSTED_PROXY_IPS")] = ""

    @model_validator(mode="after")
    def normalize_local_paths(self) -> "Settings":
        self.database_url = _normalize_sqlite_url(self.effective_database_url)
        if not self.storage_dir:
            self.storage_dir = self.effective_storage_dir
        if not Path(self.storage_dir).is_absolute():
            self.storage_dir = str((Path(__file__).resolve().parent.parent.parent / self.storage_dir).resolve())
        return self

    @property
    def cors_origin_list(self) -> list[str]:
        return [origin.strip() for origin in self.cors_origins.split(",") if origin.strip()]

    @property
    def binds_to_loopback(self) -> bool:
        return self.server_bind_host.strip().lower() in {"127.0.0.1", "::1", "localhost"}

    @property
    def allowed_host_list(self) -> list[str]:
        """Explicitly configured Host authorities, lowercased and stripped."""
        return [host.strip().lower() for host in self.allowed_hosts.split(",") if host.strip()]

    @property
    def docs_are_enabled(self) -> bool:
        if self.docs_enabled is not None:
            return self.docs_enabled
        # Packaged desktop and production both withdraw the schema explorer.
        return not (self.is_production or self.environment.lower() == "desktop")

    @property
    def trusted_proxy_ip_list(self) -> list[str]:
        return [ip.strip() for ip in self.trusted_proxy_ips.split(",") if ip.strip()]

    @property
    def is_production(self) -> bool:
        return self.environment.lower() in {"production", "prod"}

    @property
    def jwt_secret_is_default(self) -> bool:
        return not self.jwt_secret or self.jwt_secret.startswith("change-me-")

    @property
    def custody_signing_key_is_default(self) -> bool:
        return not self.custody_signing_key or self.custody_signing_key.startswith("change-me-")

    @property
    def should_create_tables(self) -> bool:
        if self.auto_create_tables is not None:
            return self.auto_create_tables
        return not self.is_production

    @property
    def public_registration_enabled(self) -> bool:
        if self.public_registration is not None:
            return self.public_registration
        return False

    @property
    def ai_configured(self) -> bool:
        if self.ai_local:
            return bool(self.ai_base_url)
        return bool(self.ai_api_key)


class _PackagedDesktopSettings(Settings):
    """Packaged desktop settings accept explicit safe values, not ambient OIHK variables."""

    @classmethod
    def settings_customise_sources(
        cls,
        settings_cls,
        init_settings,
        env_settings,
        dotenv_settings,
        file_secret_settings,
    ):
        # Pydantic calls this hook with a fixed signature; packaged desktop
        # mode intentionally accepts constructor values only.
        del settings_cls, env_settings, dotenv_settings, file_secret_settings
        return (init_settings,)


@lru_cache
def get_settings() -> Settings:
    if os.environ.get("OIHK_DESKTOP_PACKAGED") == "1":
        data_dir_value = os.environ.get("OIHK_PACKAGED_DATA_DIR", "")
        overrides: dict[str, object] = {
            "environment": "desktop",
            "auth_enabled": False,
            "cors_origins": "http://tauri.localhost,tauri://localhost",
            "server_bind_host": "127.0.0.1",
        }
        if data_dir_value:
            data_dir = Path(data_dir_value).resolve()
            overrides["database_url"] = f"sqlite+aiosqlite:///{(data_dir / 'oihk-basic.db').as_posix()}"
            overrides["storage_dir"] = str(data_dir / "storage")
        return _PackagedDesktopSettings(**overrides)
    return Settings()
