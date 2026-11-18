"""Application configuration loaded from environment variables.

Secrets (JWT_SECRET, SECRET_KEY, SUPABASE_SERVICE_ROLE_KEY, GEMINI_API_KEY)
are server-side only and must never be sent to the frontend.
"""
from __future__ import annotations

import logging
import secrets
from functools import lru_cache
from pathlib import Path
from typing import Literal

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

log = logging.getLogger("ledgerflow.config")

BACKEND_ROOT = Path(__file__).resolve().parents[2]


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=(BACKEND_ROOT.parent / ".env", BACKEND_ROOT / ".env"),
        env_file_encoding="utf-8",
        extra="ignore",
    )

    APP_ENV: Literal["development", "test", "staging", "production"] = "development"
    APP_NAME: str = "LedgerFlow AI"
    LOG_LEVEL: str = "INFO"

    # Database: PostgreSQL (Supabase) in hosted environments, SQLite locally.
    DATABASE_URL: str = f"sqlite:///{(BACKEND_ROOT / 'ledgerflow.db').as_posix()}"

    # Supabase (optional). Service-role key is used ONLY server-side for Storage.
    SUPABASE_URL: str = ""
    SUPABASE_ANON_KEY: str = ""
    SUPABASE_SERVICE_ROLE_KEY: str = ""
    SUPABASE_STORAGE_BUCKET: str = "ledgerflow-documents"

    SECRET_KEY: str = ""
    JWT_SECRET: str = ""
    JWT_EXPIRE_MINUTES: int = 60 * 8
    AUTH_COOKIE_NAME: str = "lf_session"
    AUTH_COOKIE_SECURE: bool = False

    # AI
    AI_PROVIDER: Literal["rules", "ollama", "gemini"] = "rules"
    AI_TIMEOUT_SECONDS: float = 45.0
    OLLAMA_BASE_URL: str = "http://localhost:11434"
    OLLAMA_MODEL: str = "qwen2.5:0.5b-instruct"
    OLLAMA_NUM_CTX: int = 1024
    GEMINI_API_KEY: str = ""
    GEMINI_MODEL: str = "gemini-2.0-flash"
    # Cloud AI must be explicitly acknowledged; documents leave the machine.
    ALLOW_CLOUD_AI: bool = False

    # OCR
    OCR_ENGINE: Literal["tesseract", "none"] = "tesseract"
    TESSERACT_CMD: str = ""
    OCR_DPI: int = 200

    # Storage
    STORAGE_PROVIDER: Literal["local", "supabase"] = "local"
    LOCAL_STORAGE_PATH: str = str(BACKEND_ROOT / "storage")
    MAX_UPLOAD_MB: int = 10
    MAX_PDF_PAGES: int = 10

    # Number of trusted reverse proxies in front of the API that append to X-Forwarded-For
    # (e.g. Vercel rewrite -> Render load balancer). 0 = use the socket peer address.
    TRUSTED_PROXY_HOPS: int = 0

    FRONTEND_URL: str = "http://localhost:3000"
    BACKEND_URL: str = "http://localhost:8000"

    DEMO_MODE: bool = True
    # Seed the demo company on container start if it does not exist (hosted demos only).
    SEED_DEMO_ON_START: bool = False

    # Encryption at rest for MFA secrets (Fernet key). Required outside development.
    ENCRYPTION_KEY: str = ""

    # Email: console (dev, prints to log) | smtp | brevo | none
    EMAIL_PROVIDER: Literal["console", "smtp", "brevo", "none"] = "console"
    EMAIL_FROM: str = "no-reply@ledgerflow.example"
    EMAIL_FROM_NAME: str = "LedgerFlow AI"
    EMAIL_TIMEOUT_SECONDS: float = 15.0
    SMTP_HOST: str = ""
    SMTP_PORT: int = 587
    SMTP_USERNAME: str = ""
    SMTP_PASSWORD: str = ""
    SMTP_SECURITY: Literal["starttls", "ssl", "none"] = "starttls"
    BREVO_API_KEY: str = ""
    # Public URL of the frontend used in email links (defaults to the first FRONTEND_URL).
    APP_PUBLIC_URL: str = ""

    # Two-factor authentication
    MFA_ISSUER: str = "LedgerFlow AI"

    # Malware scanning: none | clamav. PDF active-content blocking is always on.
    MALWARE_SCANNER: Literal["none", "clamav"] = "none"
    CLAMAV_HOST: str = "127.0.0.1"
    CLAMAV_PORT: int = 3310
    CLAMAV_TIMEOUT_SECONDS: float = 30.0
    # Reject uploads when the configured scanner is unreachable (recommended).
    MALWARE_SCAN_FAIL_CLOSED: bool = True

    # Backups
    BACKUP_ENCRYPTION_KEY: str = ""
    BACKUP_DESTINATION: Literal["local", "supabase"] = "local"
    BACKUP_LOCAL_PATH: str = str(BACKEND_ROOT / "backups")
    BACKUP_BUCKET: str = "ledgerflow-backups"
    BACKUP_KEEP: int = 14

    # Financial validation defaults (company settings may override)
    AMOUNT_TOLERANCE: str = "1.00"

    @field_validator("*", mode="after")
    @classmethod
    def _strip_whitespace(cls, v):
        # Pasted secrets often carry a trailing newline or space, which makes HTTP headers illegal
        # (httpx LocalProtocolError) or silently breaks comparisons. Trim every string setting.
        return v.strip() if isinstance(v, str) else v

    @field_validator("DATABASE_URL")
    @classmethod
    def _normalise_pg(cls, v: str) -> str:
        # Supabase gives postgres:// URLs; SQLAlchemy needs postgresql://
        if v.startswith("postgres://"):
            v = "postgresql://" + v[len("postgres://"):]
        return v

    @property
    def is_sqlite(self) -> bool:
        return self.DATABASE_URL.startswith("sqlite")

    @property
    def is_production(self) -> bool:
        return self.APP_ENV in ("staging", "production")

    @property
    def public_url(self) -> str:
        return (self.APP_PUBLIC_URL or self.FRONTEND_URL.split(",")[0]).rstrip("/")


@lru_cache
def get_settings() -> Settings:
    s = Settings()
    if not s.JWT_SECRET or not s.SECRET_KEY:
        if s.is_production:
            raise RuntimeError("JWT_SECRET and SECRET_KEY must be set outside development.")
        # Development convenience: ephemeral secrets (sessions reset on restart).
        log.warning("JWT_SECRET/SECRET_KEY not set; using ephemeral development secrets.")
        s.JWT_SECRET = s.JWT_SECRET or secrets.token_urlsafe(48)
        s.SECRET_KEY = s.SECRET_KEY or secrets.token_urlsafe(48)
    if s.is_production and len(s.JWT_SECRET) < 32:
        raise RuntimeError("JWT_SECRET must be at least 32 characters.")
    if s.is_production:
        s.AUTH_COOKIE_SECURE = True
        if not s.ENCRYPTION_KEY:
            raise RuntimeError("ENCRYPTION_KEY must be set outside development (protects MFA secrets).")
        if s.EMAIL_PROVIDER == "console":
            log.warning("EMAIL_PROVIDER=console in %s: emails are only logged (redacted), not delivered.", s.APP_ENV)
    return s


settings = get_settings()
