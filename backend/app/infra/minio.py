"""MinIO blob storage adapter for original TIFFs and overlay PNGs."""

from __future__ import annotations

import os
from io import BytesIO

from minio import Minio, S3Error
from minio.commonconfig import CopySource


class MinIOError(Exception):
    """Base exception for MinIO adapter operations."""


class MinIOConnectionError(MinIOError):
    """Raised when the MinIO server is unreachable."""


class MinIOPermissionError(MinIOError):
    """Raised when credentials lack required permissions."""


class MinIOBucketError(MinIOError):
    """Raised when a bucket operation fails."""


class MinIOFileNotFoundError(MinIOError):
    """Raised when a requested object does not exist."""


# MinIO bucket name for storing original scanner TIFFs before classification
ORIGINALS_BUCKET = "originals"
# MinIO bucket name for storing annotated overlay PNGs after classification
OVERLAYS_BUCKET = "overlays"


class MinIOAdapter:
    """Adapter for MinIO blob storage operations.

    Manages bucket bootstrap for originals and overlays, and provides
    upload, download, and existence-check operations for TIFF and PNG
    objects.
    """

    def __init__(
        self,
        endpoint: str | None = None,
        access_key: str | None = None,
        secret_key: str | None = None,
        secure: bool = False,
    ):
        """Initialize the MinIO adapter.

        Args:
            endpoint: MinIO server endpoint. Falls back to MINIO_ENDPOINT env var.
            access_key: MinIO access key. Falls back to MINIO_ROOT_USER env var.
            secret_key: MinIO secret key. Falls back to MINIO_ROOT_PASSWORD env var.
            secure: Whether to use HTTPS. Defaults to False for local dev.
        """
        self._endpoint = endpoint or os.environ.get("MINIO_ENDPOINT", "localhost:9000")
        self._access_key = access_key or os.environ.get("MINIO_ROOT_USER", "minioadmin")
        self._secret_key = secret_key or os.environ.get(
            "MINIO_ROOT_PASSWORD", "minioadmin"
        )
        self._secure = secure

        try:
            self._client = Minio(
                endpoint=self._endpoint,
                access_key=self._access_key,
                secret_key=self._secret_key,
                secure=self._secure,
            )
        except Exception as exc:
            raise MinIOConnectionError(
                f"Failed to create MinIO client for {self._endpoint}: {exc}"
            ) from exc

    def ensure_buckets_exist(self) -> None:
        """Create or validate the originals and overlays buckets.

        Checks if both required buckets exist, creating any that are
        missing. Idempotent – safe to call on every startup.

        Raises:
            MinIOConnectionError: If the MinIO server is unreachable.
            MinIOPermissionError: If credentials lack bucket creation rights.
            MinIOBucketError: If a bucket operation fails for other reasons.
        """
        for bucket in (ORIGINALS_BUCKET, OVERLAYS_BUCKET):
            self._ensure_bucket(bucket)

    def upload_file(self, bucket: str, key: str, data: bytes, content_type: str) -> str:
        """Upload an object to a MinIO bucket.

        Args:
            bucket: Target bucket name.
            key: Object key (path) within the bucket.
            data: Raw bytes to upload.
            content_type: MIME type (e.g. 'image/tiff', 'image/png').

        Returns:
            The object key on success.

        Raises:
            MinIOConnectionError: If the MinIO server is unreachable.
            MinIOPermissionError: If write access is denied.
            MinIOBucketError: If the bucket does not exist.
        """
        try:
            self._client.put_object(
                bucket_name=bucket,
                object_name=key,
                data=BytesIO(data),
                length=len(data),
                content_type=content_type,
            )
        except S3Error as exc:
            self._raise_typed_error(f"Failed to upload '{key}' to '{bucket}'", exc)
        return key

    def download_file(self, bucket: str, key: str) -> bytes:
        """Download an object from a MinIO bucket.

        Args:
            bucket: Source bucket name.
            key: Object key to download.

        Returns:
            The object content as bytes.

        Raises:
            MinIOFileNotFoundError: If the object does not exist.
            MinIOConnectionError: If the MinIO server is unreachable.
            MinIOPermissionError: If read access is denied.
        """
        try:
            response = self._client.get_object(
                bucket_name=bucket,
                object_name=key,
            )
        except S3Error as exc:
            self._raise_typed_error(f"Failed to download '{key}' from '{bucket}'", exc)
            raise

        try:
            return response.read()
        finally:
            response.close()
            response.release_conn()

    def file_exists(self, bucket: str, key: str) -> bool:
        """Check whether an object exists in a bucket.

        Args:
            bucket: Bucket name.
            key: Object key to check.

        Returns:
            True if the object exists, False otherwise.

        Raises:
            MinIOConnectionError: If the MinIO server is unreachable.
        """
        try:
            self._client.stat_object(bucket_name=bucket, object_name=key)
            return True
        except S3Error as exc:
            if exc.code == "NoSuchKey":
                return False
            self._raise_typed_error(f"Failed to stat '{key}' in '{bucket}'", exc)
            return False

    def _ensure_bucket(self, bucket: str) -> None:
        """Create a bucket if it does not already exist.

        Args:
            bucket: Bucket name to check and potentially create.

        Raises:
            MinIOConnectionError: Server unreachable.
            MinIOPermissionError: Access denied.
            MinIOBucketError: Other bucket operation failure.
        """
        try:
            exists = self._client.bucket_exists(bucket)
        except S3Error as exc:
            self._raise_typed_error(f"Failed to check bucket '{bucket}'", exc)
            return

        if not exists:
            try:
                self._client.make_bucket(bucket)
            except S3Error as exc:
                self._raise_typed_error(f"Failed to create bucket '{bucket}'", exc)

    @staticmethod
    def _raise_typed_error(msg: str, exc: S3Error) -> None:
        """Convert an S3Error into the appropriate typed MinIO exception.

        Args:
            msg: Context message describing the operation.
            exc: The S3Error raised by the MinIO client.

        Raises:
            MinIOPermissionError: For AccessDenied errors.
            MinIOBucketError: For NoSuchBucket or BucketAlreadyOwnedByYou.
            MinIOFileNotFoundError: For NoSuchKey errors.
            MinIOConnectionError: For all other S3Errors.
        """
        if exc.code == "AccessDenied":
            raise MinIOPermissionError(f"{msg}: access denied") from exc
        if exc.code in ("NoSuchBucket", "BucketAlreadyOwnedByYou"):
            raise MinIOBucketError(f"{msg}: {exc.code}") from exc
        if exc.code == "NoSuchKey":
            raise MinIOFileNotFoundError(f"{msg}: not found") from exc
        raise MinIOConnectionError(f"{msg}: {exc}") from exc


# ------------------------------------------------------------------
# Module-level functions — called by services and startup validation
# ------------------------------------------------------------------


def upload_original(document_id: str, data: bytes) -> tuple[str, str]:
    """Upload an original TIFF to MinIO and return (bucket, key).

    Convenience wrapper called by IngestionService.ingest_file().

    Args:
        document_id: UUID string of the document record.
        data: Raw TIFF bytes.

    Returns:
        Tuple of (bucket_name, object_key).
    """
    adapter = MinIOAdapter()
    key = f"{document_id}.tiff"
    adapter.upload_file(ORIGINALS_BUCKET, key, data, "image/tiff")
    return (ORIGINALS_BUCKET, key)


def ensure_buckets() -> None:
    """Create or validate originals and overlays buckets.

    Module-level alias called by startup validation.
    Idempotent — safe to call on every startup.
    """
    MinIOAdapter().ensure_buckets_exist()


def check_originals_writable() -> None:
    """Verify the originals bucket is writable.

    Uploads a tiny probe object to confirm write access.
    Called by ingestion worker startup validation.
    """
    adapter = MinIOAdapter()
    probe_data = b"startup-probe"
    probe_key = "_startup_probe_.tiff"
    adapter.upload_file(ORIGINALS_BUCKET, probe_key, probe_data, "image/tiff")
