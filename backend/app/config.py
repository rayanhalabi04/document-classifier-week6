"""Centralised application settings loaded from environment variables.

All configuration is validated on first access. Every module that previously
called os.environ.get() should import `settings` from this module instead.
"""

from __future__ import annotations

from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    # ── Postgres ──────────────────────────────────────────────
    database_url: str = "postgresql://postgres:changeme@postgres:5432/document_classifier"

    # ── Redis ─────────────────────────────────────────────────
    redis_url: str = "redis://redis:6379/0"

    # ── Vault ─────────────────────────────────────────────────
    vault_addr: str = "http://vault:8200"
    vault_token: str = "root"

    # ── MinIO ─────────────────────────────────────────────────
    minio_endpoint: str = "minio:9000"
    minio_root_user: str = "minioadmin"
    minio_root_password: str = "minioadmin"
    minio_bucket_originals: str = "originals"
    minio_bucket_overlays: str = "overlays"

    # ── SFTP ──────────────────────────────────────────────────
    sftp_host: str = "sftp"
    sftp_port: int = 22
    sftp_user: str = "vendor"
    sftp_password: str = "vendorpass"
    sftp_drop_dir: str = "drop"

    # ── JWT ───────────────────────────────────────────────────
    jwt_secret: str = "change-me-in-production"

    # ── Ingestion Worker ──────────────────────────────────────
    ingestion_poll_interval: int = 5
    ingestion_stability_interval: int = 3

    # ── Logging ───────────────────────────────────────────────
    log_level: str = "INFO"
    log_format: str = "console"

    model_config = {"env_prefix": "", "case_sensitive": False}


settings = Settings()
