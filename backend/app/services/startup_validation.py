"""Startup validation service — fail-fast checks for required dependencies.

Called by /health/ready and by worker startup routines. Each check raises
StartupValidationError with a safe message on failure. No credentials or
infrastructure internals are included in error messages.
"""

import logging

from app.domain.errors import StartupValidationError

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# API readiness checks
# ---------------------------------------------------------------------------


def check_postgres(session_factory) -> None:
    """Verify Postgres is reachable and Alembic head migration is applied."""
    try:
        from sqlalchemy import text

        with session_factory() as session:
            session.execute(text("SELECT 1"))
    except Exception as exc:
        raise StartupValidationError("Postgres connection failed.") from exc

    try:
        from alembic.config import Config
        from alembic.runtime.migration import MigrationContext
        from alembic.script import ScriptDirectory

        cfg = Config("alembic.ini")
        script = ScriptDirectory.from_config(cfg)
        with session_factory() as session:
            conn = session.connection()
            context = MigrationContext.configure(conn)
            current = context.get_current_revision()
            head = script.get_current_head()
            if current != head:
                raise StartupValidationError(
                    f"Database migration not at head (current={current}, head={head})."
                )
    except StartupValidationError:
        raise
    except Exception as exc:
        raise StartupValidationError("Alembic migration check failed.") from exc


def check_redis() -> None:
    """Verify Redis 7 is reachable."""
    try:
        from app.infra.redis import get_redis_client

        client = get_redis_client()
        client.ping()
    except Exception as exc:
        raise StartupValidationError("Redis connection failed.") from exc


def check_minio_buckets() -> None:
    """Verify MinIO originals and overlays buckets exist or can be created."""
    try:
        from app.infra.minio import ensure_buckets

        ensure_buckets()
    except Exception as exc:
        raise StartupValidationError("MinIO bucket bootstrap failed.") from exc


def check_vault() -> None:
    """Verify Vault dev mode KV v2 path is reachable and required secrets exist."""
    try:
        from app.infra.vault import validate_required_secrets

        validate_required_secrets()
    except Exception as exc:
        raise StartupValidationError("Vault secrets validation failed.") from exc


def check_casbin(session_factory) -> None:
    """Verify Casbin policy storage is reachable and baseline policies are loaded."""
    try:
        from app.services.startup_authorization import validate_authorization_startup

        with session_factory() as session:
            validate_authorization_startup(session)
    except StartupValidationError:
        raise
    except Exception as exc:
        raise StartupValidationError("Casbin policy check failed.") from exc


def check_jwt_secret() -> None:
    """Verify the Vault JWT secret is present and not a placeholder."""
    try:
        from app.services.auth import load_jwt_secret

        secret = load_jwt_secret()
    except Exception as exc:
        raise StartupValidationError("JWT Vault secret is missing.") from exc

    if not secret or secret in (
        "changeme",
        "change-me",
        "change-me-in-production",
        "secret",
        "your-secret-here",
    ):
        raise StartupValidationError("JWT Vault secret is a placeholder.")


def run_api_readiness_checks(session_factory) -> list[str]:
    """Run all API startup checks. Returns list of failed check messages."""
    checks = [
        ("postgres", lambda: check_postgres(session_factory)),
        ("redis", check_redis),
        ("minio_buckets", check_minio_buckets),
        ("vault", check_vault),
        ("casbin", lambda: check_casbin(session_factory)),
        ("jwt_secret", check_jwt_secret),
    ]
    failures = []
    for name, check in checks:
        try:
            check()
            logger.info("Startup check passed: %s", name)
        except StartupValidationError as exc:
            logger.error("Startup check failed: %s — %s", name, exc)
            failures.append(f"{name}: {exc}")
    return failures


# ---------------------------------------------------------------------------
# Ingestion worker readiness checks
# ---------------------------------------------------------------------------


def check_sftp() -> None:
    """Verify SFTP connection and vendor drop directory is readable."""
    try:
        from app.infra.sftp import check_connection

        check_connection()
    except Exception as exc:
        raise StartupValidationError(
            "SFTP connection or directory check failed."
        ) from exc


def check_minio_originals_writable() -> None:
    """Verify the originals bucket is writable."""
    try:
        from app.infra.minio import check_originals_writable

        check_originals_writable()
    except Exception as exc:
        raise StartupValidationError("MinIO originals bucket is not writable.") from exc


def check_rq_available() -> None:
    """Verify the Redis Queue enqueue path is available."""
    try:
        from app.infra.queue import check_queue_health

        check_queue_health()
    except Exception as exc:
        raise StartupValidationError("Redis Queue is not available.") from exc


def run_ingestion_worker_checks() -> list[str]:
    """Run ingestion worker startup checks. Returns list of failed check messages."""
    checks = [
        ("sftp", check_sftp),
        ("minio_buckets", check_minio_buckets),
        ("minio_originals_writable", check_minio_originals_writable),
        ("rq_queue", check_rq_available),
    ]
    failures = []
    for name, check in checks:
        try:
            check()
            logger.info("Ingestion worker check passed: %s", name)
        except StartupValidationError as exc:
            logger.error("Ingestion worker check failed: %s — %s", name, exc)
            failures.append(f"{name}: {exc}")
    return failures


# ---------------------------------------------------------------------------
# Inference worker readiness checks
# ---------------------------------------------------------------------------


def check_classifier_assets() -> None:
    """Verify classifier.pt and model_card.json exist, parse, and match checksums."""
    try:
        from app.classifier.validation import validate_classifier_assets

        validate_classifier_assets()
    except Exception as exc:
        raise StartupValidationError("Classifier asset validation failed.") from exc


def run_inference_worker_checks() -> list[str]:
    """Run inference worker startup checks. Returns list of failed check messages."""
    checks = [
        ("classifier_assets", check_classifier_assets),
        ("minio_buckets", check_minio_buckets),
        ("minio_originals_writable", check_minio_originals_writable),
        ("rq_queue", check_rq_available),
        ("redis", check_redis),
    ]
    failures = []
    for name, check in checks:
        try:
            check()
            logger.info("Inference worker check passed: %s", name)
        except StartupValidationError as exc:
            logger.error("Inference worker check failed: %s — %s", name, exc)
            failures.append(f"{name}: {exc}")
    return failures
