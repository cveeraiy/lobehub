"""Centralised application settings via pydantic-settings.

All configuration is read from environment variables (or a `.env` file).
Import the singleton ``settings`` wherever configuration is needed:

    from app.config import settings
"""

from __future__ import annotations

from functools import lru_cache
from typing import Optional

from pydantic import Field, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Flat settings object — every field maps to an env var."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # ── General ────────────────────────────────────────────────────────
    debug: bool = False
    log_level: str = "INFO"

    # ── Database ───────────────────────────────────────────────────────
    database_url: str = "postgresql+asyncpg://postgres:postgres@localhost:5432/lobehub"

    # ── Key vaults ─────────────────────────────────────────────────────
    # Fernet-compatible key used to encrypt/decrypt provider API keys
    # Generate with: python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
    key_vaults_secret: Optional[str] = None

    # ── Auth (Keycloak / Generic OIDC) ─────────────────────────────────
    # OIDC discovery URL, e.g. https://keycloak.example.com/realms/lobehub
    auth_oidc_issuer: Optional[str] = None
    # Client ID registered in Keycloak for this backend
    auth_oidc_client_id: str = "lobehub-backend"
    # Optional audience claim to validate (defaults to client_id)
    auth_oidc_audience: Optional[str] = None
    # JWKS URI override (auto-discovered from issuer if not set)
    auth_oidc_jwks_uri: Optional[str] = None
    # Algorithms accepted for JWT validation
    auth_oidc_algorithms: str = "RS256"
    # Client secret for authorization code flow (required for login)
    auth_oidc_client_secret: Optional[str] = None
    # Scopes to request from Keycloak
    auth_oidc_scopes: str = "openid email profile"

    # ── App URL ──────────────────────────────────────────────────────────
    # Public URL of this app (used for OIDC redirect URIs)
    app_url: str = "http://localhost:9876"

    # Disable email/password login — only SSO (Keycloak) allowed
    auth_disable_email_password: bool = True

    # ── Session ──────────────────────────────────────────────────────────
    # Secret key for signing session cookies (min 32 chars)
    # Generate with: python -c "import secrets; print(secrets.token_urlsafe(32))"
    session_secret: str = "change-me-in-production-use-a-real-secret-key"

    @model_validator(mode="after")
    def _resolve_oidc_defaults(self) -> "Settings":
        if self.auth_oidc_audience is None:
            self.auth_oidc_audience = self.auth_oidc_client_id
        if self.auth_oidc_issuer and self.auth_oidc_jwks_uri is None:
            issuer = self.auth_oidc_issuer.rstrip("/")
            self.auth_oidc_jwks_uri = f"{issuer}/protocol/openid-connect/certs"
        return self

    # ── S3 / MinIO ─────────────────────────────────────────────────────
    s3_access_key_id: Optional[str] = None
    s3_secret_access_key: Optional[str] = None
    s3_endpoint: Optional[str] = None
    s3_bucket: str = "lobehub"
    s3_region: Optional[str] = None
    # Public URL prefix used to build download links
    s3_public_domain: Optional[str] = None

    # ── LLM defaults ───────────────────────────────────────────────────
    openai_api_key: Optional[str] = None
    openai_proxy_url: Optional[str] = None

    # ── AWS Bedrock ─────────────────────────────────────────────────────
    aws_access_key_id: Optional[str] = None
    aws_secret_access_key: Optional[str] = None
    aws_region: Optional[str] = None

    # ── Embedding ──────────────────────────────────────────────────────
    embedding_batch_size: int = 50
    embedding_concurrency: int = 10
    default_files_config: Optional[str] = None

    # ── Langfuse (tracing) ───────────────────────────────────────
    langfuse_public_key: Optional[str] = None
    langfuse_secret_key: Optional[str] = None
    langfuse_host: str = "https://cloud.langfuse.com"
    langfuse_enabled: bool = False

    # ── Web Search ──────────────────────────────────────────────
    # Comma-separated provider chain: "tavily,brave,searxng" etc.
    # If unset, auto-detects from available API keys.
    search_providers: Optional[str] = None
    # Legacy alias (kept for backward compat)
    search_provider: Optional[str] = None
    # Provider API keys
    tavily_api_key: Optional[str] = None
    brave_api_key: Optional[str] = None
    google_pse_api_key: Optional[str] = None
    google_pse_engine_id: Optional[str] = None
    exa_api_key: Optional[str] = None
    searxng_url: Optional[str] = None  # e.g. http://localhost:8888
    jina_api_key: Optional[str] = None
    firecrawl_api_key: Optional[str] = None
    firecrawl_url: Optional[str] = None  # custom instance URL
    kagi_api_key: Optional[str] = None
    bocha_api_key: Optional[str] = None
    search1api_api_key: Optional[str] = None
    anspire_api_key: Optional[str] = None
    serper_api_key: Optional[str] = None

    # ── Code Interpreter ──────────────────────────────────────────
    code_interpreter_enabled: bool = True
    code_interpreter_timeout: int = 30  # seconds
    # Sandbox mode: "docker" (recommended), "subprocess" (dev-only, insecure)
    code_interpreter_sandbox: str = "subprocess"
    # Docker image for sandboxed execution (must have python3 installed)
    code_interpreter_docker_image: str = "python:3.12-slim"
    # Max memory for sandbox container
    code_interpreter_memory_limit: str = "256m"
    # Docker network mode for self-hosted sandbox containers. Use "none" for
    # strict isolation, or "bridge" when sandbox commands need outbound access.
    cloud_sandbox_docker_network: str = "none"
    # Root directory for self-hosted Cloud Sandbox workspaces
    cloud_sandbox_root: Optional[str] = None

    # ── URL safety (SSRF protection) ──────────────────────────────
    # Comma-separated allowed URL schemes for tool fetches
    allowed_url_schemes: str = "https"
    # Comma-separated domain allowlist for skill imports (empty = any public domain)
    skill_import_domain_allowlist: str = ""

    # ── Skills / MCP ──────────────────────────────────────────────
    # Enables official Ethos Skill providers in the SPA. Custom skills and MCP
    # endpoints are served by the Python backend independently of this switch.
    enable_lobehub_skill: bool = True
    # Klavis requires a real API key; keep the UI gate credential-aware.
    klavis_api_key: Optional[str] = None

    # ── Tool rate limiting ──────────────────────────────────────────
    # Max external API calls per minute per user (0 = no limit)
    tool_rate_limit_per_minute: int = 60

    # ── Agent Runtime ───────────────────────────────────────────
    agent_max_steps: int = 25
    agent_require_human_approval: bool = False

    # ── Content Policy ────────────────────────────────────────────
    content_policy_enabled: bool = False
    content_policy_use_moderation_api: bool = False
    content_policy_check_output: bool = True
    content_policy_blocked_patterns: str = ""  # comma-separated regex patterns

    # ── Internal service token (TS ↔ Python proxy auth) ──────────
    # Shared secret between the TS backend and this Python backend.
    # When set, requests with a valid X-Service-Token header bypass OIDC
    # JWT validation and trust the X-Internal-User-Id header instead.
    # Generate with: python -c "import secrets; print(secrets.token_urlsafe(32))"
    python_backend_service_token: Optional[str] = None

    # ── Feature flags ────────────────────────────────────────────
    # Comma-separated: "+flag_name" to enable, "-flag_name" to disable
    feature_flags: str = ""

    # ── Temporal workflows ───────────────────────────────────────
    # Durable self-hosted replacement for QStash workflow transport.
    temporal_enabled: bool = False
    temporal_address: str = "localhost:7233"
    temporal_namespace: str = "default"
    temporal_task_queue: str = "ethos-workflows"
    temporal_workflow_timeout_seconds: int = 3600
    temporal_activity_timeout_seconds: int = 900
    temporal_fallback_to_inline: bool = True


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    """Return a cached singleton of the application settings."""
    return Settings()


settings: Settings = get_settings()
