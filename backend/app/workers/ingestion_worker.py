"""Ingestion worker — polls SFTP, detects stable TIFFs, ingests into the pipeline.

Startup:
    1. Validates SFTP, MinIO, and Redis Queue readiness.
    2. Exits fast if any check fails.

Main loop:
    1. Polls the SFTP vendor drop directory.
    2. Detects files that are still being written by requiring stable size
       and modified timestamp across polling intervals (T025).
    3. Rejects unsupported, corrupted, or non-TIFF files (T026).
    4. Skips duplicates (already-active source + checksum combinations).
    5. For accepted files: uploads to MinIO, enqueues RQ job, records state.
    6. Continues after per-file failures — never stops the loop (T027).
"""

from __future__ import annotations

import hashlib
import logging
import signal
import sys
import time
import uuid
from dataclasses import dataclass
from datetime import datetime, timezone

from app.config import settings
from app.db.session import SessionFactory
from app.domain.errors import (
    DuplicateDocumentError,
    StorageError,
    UnsupportedFileTypeError,
)
from app.infra.sftp import SFTPAdapter, SFTPFileInfo
from app.repositories.model_metadata import ModelMetadataRepository
from app.services.ingestion import IngestionService
from app.services.startup_validation import run_ingestion_worker_checks

logger = logging.getLogger(__name__)

POLL_INTERVAL_SECONDS = settings.ingestion_poll_interval
STABILITY_INTERVAL_SECONDS = settings.ingestion_stability_interval
SFTP_DROP_DIR = settings.sftp_drop_dir
_BACKOFF_BASE_SECONDS = POLL_INTERVAL_SECONDS
_BACKOFF_CAP_SECONDS = 60


@dataclass
class _SeenFile:
    """Tracks a previously observed file for stable-file detection.

    Attributes:
        size_bytes: File size observed in the last poll cycle.
        modified_at: Last modification timestamp observed.
        When both match across two consecutive polls, the file is
        considered "stable" (the scanner has finished writing it).
    """

    size_bytes: int
    modified_at: datetime


def _compute_checksum(data: bytes) -> str:
    """Return the SHA-256 hex digest of a file's content.

    Used for duplicate detection: files with the same source_path
    and checksum are treated as duplicates and skipped.
    """
    return hashlib.sha256(data).hexdigest()


def _get_model_metadata_id(session) -> uuid.UUID | None:
    """Look up the latest model metadata record."""
    repo = ModelMetadataRepository(session)
    latest = repo.get_latest()
    if latest is None:
        logger.error("No model metadata record found. Worker cannot enqueue jobs.")
        return None
    return latest.id


def _run_startup_checks() -> bool:
    """Run ingestion worker startup checks. Returns True if all pass."""
    logger.info("Running ingestion worker startup checks ...")
    failures = run_ingestion_worker_checks()
    if failures:
        for f in failures:
            logger.error("Startup check FAILED: %s", f)
        logger.error("Worker aborting — %d startup check(s) failed.", len(failures))
        return False
    logger.info("All startup checks passed.")
    return True


def _detect_stable_files(
    sftp: SFTPAdapter,
    seen_files: dict[str, _SeenFile],
) -> list[SFTPFileInfo]:
    """Find files that are stable (size + mtime unchanged since last poll).

    T025: Worker avoids ingesting files still being written by the scanner.
    A file is "stable" when its size and modified timestamp match the
    values observed in the previous poll cycle. Newly discovered files
    are recorded and deferred to the next cycle.

    Args:
        sftp: Connected SFTP adapter.
        seen_files: Dict of filename -> previously observed metadata.

    Returns:
        List of SFTPFileInfo for files confirmed stable this cycle.
    """
    try:
        current_files = sftp.list_files(SFTP_DROP_DIR)
    except Exception as exc:
        logger.warning("Failed to list SFTP directory: %s", exc)
        return []

    stable: list[SFTPFileInfo] = []
    current_filenames: set[str] = set()

    for f in current_files:
        current_filenames.add(f.filename)
        prev = seen_files.get(f.filename)

        if prev is None:
            # First time seeing this file — record it, check again next poll
            seen_files[f.filename] = _SeenFile(
                size_bytes=f.size_bytes,
                modified_at=f.modified_at,
            )
            logger.debug(
                "New file detected: %s (%d bytes), waiting for stability ...",
                f.filename,
                f.size_bytes,
            )
            continue

        if f.size_bytes == prev.size_bytes and f.modified_at == prev.modified_at:
            # Size and timestamp unchanged — file is stable
            stable.append(f)
            logger.info("File is stable: %s (%d bytes)", f.filename, f.size_bytes)
        else:
            # File changed since last poll — update tracking, check next cycle
            seen_files[f.filename] = _SeenFile(
                size_bytes=f.size_bytes,
                modified_at=f.modified_at,
            )
            logger.debug(
                "File still changing: %s (%d→%d bytes)",
                f.filename,
                prev.size_bytes,
                f.size_bytes,
            )

    # Purge tracking for files that disappeared from the directory
    for filename in list(seen_files.keys()):
        if filename not in current_filenames:
            del seen_files[filename]

    return stable


def _process_file(
    sftp: SFTPAdapter,
    file_info: SFTPFileInfo,
    service: IngestionService,
    model_metadata_id: uuid.UUID,
) -> None:
    """Process a single stable file through the ingestion pipeline.

    T026: Handles edge cases:
    - Unsupported/non-TIFF files → marked failed, audited.
    - Duplicate source+checksum → skipped, no duplicate active prediction.
    - Storage failures → retried on next poll if visible.
    """
    try:
        file_data = sftp.read_file_content(file_info.remote_path)
    except Exception as exc:
        logger.warning(
            "Failed to read file content for %s: %s", file_info.filename, exc
        )
        return

    try:
        service.ingest_file(
            source_path=file_info.remote_path,
            source_filename=file_info.filename,
            file_data=file_data,
            model_metadata_id=model_metadata_id,
            request_id=str(uuid.uuid4()),
        )
        logger.info("Successfully ingested: %s", file_info.filename)
    except UnsupportedFileTypeError as exc:
        logger.warning("Unsupported file type: %s — %s", file_info.filename, exc)
        service.mark_failed(
            source_path=file_info.remote_path,
            source_filename=file_info.filename,
            reason=str(exc),
            request_id=str(uuid.uuid4()),
        )
    except DuplicateDocumentError:
        logger.info(
            "Duplicate document skipped: %s (already active)", file_info.filename
        )
    except StorageError as exc:
        logger.error(
            "Storage error for %s: %s — will retry on next poll",
            file_info.filename,
            exc,
        )
    except Exception as exc:
        logger.error("Unexpected error ingesting %s: %s", file_info.filename, exc)


def _get_sftp_adapter() -> SFTPAdapter:
    """Build an SFTPAdapter from application settings."""
    return SFTPAdapter(
        settings.sftp_host,
        settings.sftp_port,
        settings.sftp_user,
        settings.sftp_password,
    )


def main() -> None:
    """Entry point for the ingestion worker process.

    Run via: `python -m app.workers.ingestion_worker`
    """
    from app.infra.logging import configure_logging

    configure_logging()
    logger.info("Ingestion worker starting ...")

    if not _run_startup_checks():
        sys.exit(1)

    from app.infra.authz.casbin_enforcer import spawn_policy_listener

    spawn_policy_listener()

    logger.info(
        "Ingestion worker running (poll=%ds, stability=%ds)",
        POLL_INTERVAL_SECONDS,
        STABILITY_INTERVAL_SECONDS,
    )

    shutdown_requested = False

    def _on_signal(signum: int, frame: object) -> None:
        nonlocal shutdown_requested
        logger.info(
            "Received signal %s — shutting down gracefully...", signum
        )
        shutdown_requested = True

    signal.signal(signal.SIGTERM, _on_signal)
    signal.signal(signal.SIGINT, _on_signal)

    seen_files: dict[str, _SeenFile] = {}
    consecutive_failures = 0

    while not shutdown_requested:
        try:
            sftp = _get_sftp_adapter()
            with sftp:
                # Ensure model metadata is available
                with SessionFactory() as session:
                    model_metadata_id = _get_model_metadata_id(session)
                if model_metadata_id is None:
                    logger.error(
                        "Cannot enqueue jobs without model metadata. "
                        "Seed model_metadata table first."
                    )
                    time.sleep(POLL_INTERVAL_SECONDS)
                    continue

                # Reset backoff on successful SFTP connection
                consecutive_failures = 0

                while not shutdown_requested:
                    # Fresh session per poll cycle to avoid stale connections
                    with SessionFactory() as session:
                        service = IngestionService(session)
                        stable = _detect_stable_files(sftp, seen_files)
                        for file_info in stable:
                            _process_file(sftp, file_info, service, model_metadata_id)

                    time.sleep(POLL_INTERVAL_SECONDS)
        except Exception as exc:
            if shutdown_requested:
                break
            consecutive_failures += 1
            delay = min(_BACKOFF_CAP_SECONDS, _BACKOFF_BASE_SECONDS * (2 ** (consecutive_failures - 1)))
            logger.error(
                "Ingestion worker loop error (failures=%d, retry in %ds): %s",
                consecutive_failures,
                delay,
                exc,
            )
            time.sleep(delay)

    logger.info("Ingestion worker shut down gracefully.")


if __name__ == "__main__":
    main()
