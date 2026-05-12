"""Typed domain and application errors.

No bare except blocks. Callers catch specific subtypes and handle or re-raise
with context. User-facing messages must never include stack traces, file paths,
credentials, or infrastructure secrets.
"""


class AppError(Exception):
    """Base for all application errors."""


# --- Ingestion ---

class DuplicateDocumentError(AppError):
    """Raised when a document with the same checksum and path is already active."""


class UnsupportedFileTypeError(AppError):
    """Raised when an ingested file is not a supported TIFF."""


class StorageError(AppError):
    """Raised when object storage (MinIO) upload or download fails."""


class SFTPError(AppError):
    """Raised when SFTP connection or file access fails."""


# --- Classification ---

class ClassificationError(AppError):
    """Raised when inference fails for a document."""


class ModelValidationError(AppError):
    """Raised when classifier.pt or model_card.json fails validation."""


# --- Prediction Review ---

class PredictionNotFound(AppError):
    """Raised when a prediction ID does not exist."""


class ReviewNotEligible(AppError):
    """Raised when a reviewer tries to relabel a prediction at or above 0.7 confidence."""


class InvalidReviewLabel(AppError):
    """Raised when the submitted review label is not a valid RVL-CDIP class."""


# --- Authorization ---

class PermissionDenied(AppError):
    """Raised when a user lacks the required Casbin policy for an action."""


# --- Startup ---

class StartupValidationError(AppError):
    """Raised when a required dependency or asset is missing at startup."""


# --- Cache ---

class CacheInvalidationError(AppError):
    """Raised when a Redis cache deletion fails (non-fatal — Postgres remains authoritative)."""
