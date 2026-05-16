"""Centralised application configuration.

Settings are loaded from environment variables on import.  Call
apply_vault_secrets() at process startup to overwrite defaults with
values from HashiCorp Vault.  Every other module imports `settings`
as the single source of truth.
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

    model_config = {"env_prefix": "", "case_sensitive": False}


settings = Settings()


def apply_vault_secrets() -> None:
    """Overwrite settings from HashiCorp Vault.

    Called once per process at startup.  If Vault is unreachable or
    any required secret is missing the function raises — the process
    refuses to start.
    """
    from app.infra.vault import VaultAdapter, VaultError

    try:
        vault = VaultAdapter(
            url=settings.vault_addr,
            token=settings.vault_token,
        )
        settings.jwt_secret = vault.read_secret("jwt", "secret")
        settings.redis_url = vault.read_secret("redis", "url")
        settings.minio_root_user = vault.read_secret("minio", "access_key")
        settings.minio_root_password = vault.read_secret("minio", "secret_key")
        settings.sftp_host = vault.read_secret("sftp", "host")
        settings.sftp_port = int(vault.read_secret("sftp", "port"))
        settings.sftp_user = vault.read_secret("sftp", "user")
        settings.sftp_password = vault.read_secret("sftp", "password")
    except VaultError as exc:
        raise RuntimeError(
            f"Vault secrets unavailable — refusing to start: {exc}"
        ) from exc
