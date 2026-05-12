"""Unit tests for the MinIO bucket bootstrap and blob storage adapter."""

from __future__ import annotations

from unittest.mock import Mock, patch

import pytest
from minio import S3Error

from app.infra.minio import (
    ORIGINALS_BUCKET,
    OVERLAYS_BUCKET,
    MinIOAdapter,
    MinIOBucketError,
    MinIOConnectionError,
    MinIOFileNotFoundError,
    MinIOPermissionError,
)


@pytest.fixture
def mock_minio_client() -> Mock:
    """Return a mock Minio client."""
    return Mock()


@pytest.fixture
def minio_adapter(mock_minio_client: Mock) -> MinIOAdapter:
    """Return a MinIOAdapter with a mock Minio client."""
    with patch("app.infra.minio.Minio", return_value=mock_minio_client):
        return MinIOAdapter(
            endpoint="minio:9000",
            access_key="minioadmin",
            secret_key="minioadmin",
        )


def _make_s3_error(code: str, message: str = "error") -> S3Error:
    """Create an S3Error with the given code."""
    return S3Error(
        code=code,
        message=message,
        resource="test",
        request_id="req-1",
        host_id="host-1",
        response=Mock(),
    )


class TestEnsureBucketsExist:
    """Tests for MinIOAdapter.ensure_buckets_exist."""

    def test_creates_buckets_when_missing(self, minio_adapter, mock_minio_client):
        """Given buckets don't exist, creates both originals and overlays."""
        mock_minio_client.bucket_exists.side_effect = [False, False]

        minio_adapter.ensure_buckets_exist()

        assert mock_minio_client.make_bucket.call_count == 2
        mock_minio_client.make_bucket.assert_any_call(ORIGINALS_BUCKET)
        mock_minio_client.make_bucket.assert_any_call(OVERLAYS_BUCKET)

    def test_skips_buckets_when_already_exist(self, minio_adapter, mock_minio_client):
        """Given both buckets exist, creates none."""
        mock_minio_client.bucket_exists.side_effect = [True, True]

        minio_adapter.ensure_buckets_exist()

        mock_minio_client.make_bucket.assert_not_called()

    def test_creates_only_missing_bucket(self, minio_adapter, mock_minio_client):
        """Given one bucket exists and one missing, creates only the missing one."""
        mock_minio_client.bucket_exists.side_effect = [True, False]

        minio_adapter.ensure_buckets_exist()

        mock_minio_client.make_bucket.assert_called_once_with(OVERLAYS_BUCKET)

    def test_raises_minio_connection_error_on_unreachable(self, minio_adapter, mock_minio_client):
        """Given MinIO is unreachable, raises MinIOConnectionError."""
        mock_minio_client.bucket_exists.side_effect = _make_s3_error(
            "SlowDown", "server busy"
        )

        with pytest.raises(MinIOConnectionError):
            minio_adapter.ensure_buckets_exist()

    def test_raises_permission_error_on_access_denied(self, minio_adapter, mock_minio_client):
        """Given access is denied when checking buckets, raises MinIOPermissionError."""
        mock_minio_client.bucket_exists.side_effect = _make_s3_error(
            "AccessDenied", "forbidden"
        )

        with pytest.raises(MinIOPermissionError):
            minio_adapter.ensure_buckets_exist()


class TestUploadFile:
    """Tests for MinIOAdapter.upload_file."""

    def test_uploads_file_and_returns_key(self, minio_adapter, mock_minio_client):
        """Given valid data, uploads and returns the object key."""
        data = b"\x00" * 100
        key = "batch-1/doc-1.tiff"

        result = minio_adapter.upload_file(
            bucket=ORIGINALS_BUCKET,
            key=key,
            data=data,
            content_type="image/tiff",
        )

        assert result == key
        mock_minio_client.put_object.assert_called_once()
        call_kwargs = mock_minio_client.put_object.call_args.kwargs
        assert call_kwargs["bucket_name"] == ORIGINALS_BUCKET
        assert call_kwargs["object_name"] == key
        assert call_kwargs["content_type"] == "image/tiff"
        assert call_kwargs["length"] == 100

    def test_raises_permission_error_on_upload_denied(self, minio_adapter, mock_minio_client):
        """Given write access is denied, raises MinIOPermissionError."""
        mock_minio_client.put_object.side_effect = _make_s3_error(
            "AccessDenied", "forbidden"
        )

        with pytest.raises(MinIOPermissionError):
            minio_adapter.upload_file(
                bucket=ORIGINALS_BUCKET,
                key="test.tiff",
                data=b"data",
                content_type="image/tiff",
            )

    def test_raises_bucket_error_on_nonexistent_bucket(self, minio_adapter, mock_minio_client):
        """Given the bucket does not exist, raises MinIOBucketError."""
        mock_minio_client.put_object.side_effect = _make_s3_error(
            "NoSuchBucket", "bucket missing"
        )

        with pytest.raises(MinIOBucketError):
            minio_adapter.upload_file(
                bucket="nonexistent",
                key="test.tiff",
                data=b"data",
                content_type="image/tiff",
            )


class TestDownloadFile:
    """Tests for MinIOAdapter.download_file."""

    def test_downloads_file_and_returns_bytes(self, minio_adapter, mock_minio_client):
        """Given a valid key, downloads and returns the content."""
        content = b"downloaded content"
        mock_response = Mock()
        mock_response.read.return_value = content
        mock_minio_client.get_object.return_value = mock_response

        result = minio_adapter.download_file("originals", "batch-1/doc.tiff")

        assert result == content
        mock_minio_client.get_object.assert_called_once_with(
            bucket_name="originals",
            object_name="batch-1/doc.tiff",
        )

    def test_raises_file_not_found_on_missing_key(self, minio_adapter, mock_minio_client):
        """Given a nonexistent key, raises MinIOFileNotFoundError."""
        mock_minio_client.get_object.side_effect = _make_s3_error(
            "NoSuchKey", "not found"
        )

        with pytest.raises(MinIOFileNotFoundError):
            minio_adapter.download_file("originals", "missing.tiff")


class TestFileExists:
    """Tests for MinIOAdapter.file_exists."""

    def test_returns_true_when_object_exists(self, minio_adapter, mock_minio_client):
        """Given the object exists, returns True."""
        mock_minio_client.stat_object.return_value = Mock()

        result = minio_adapter.file_exists("originals", "doc.tiff")

        assert result is True

    def test_returns_false_when_object_missing(self, minio_adapter, mock_minio_client):
        """Given the object does not exist, returns False."""
        mock_minio_client.stat_object.side_effect = _make_s3_error(
            "NoSuchKey", "not found"
        )

        result = minio_adapter.file_exists("originals", "missing.tiff")

        assert result is False

    def test_raises_connection_error_on_unreachable(self, minio_adapter, mock_minio_client):
        """Given MinIO is unreachable, raises MinIOConnectionError."""
        mock_minio_client.stat_object.side_effect = _make_s3_error(
            "ServiceUnavailable", "down"
        )

        with pytest.raises(MinIOConnectionError):
            minio_adapter.file_exists("originals", "doc.tiff")


class TestMinIOAdapterInit:
    """Tests for MinIOAdapter initialization."""

    def test_raises_connection_error_when_client_creation_fails(self):
        """When the MinIO client cannot be created, raises MinIOConnectionError."""
        with patch("app.infra.minio.Minio", side_effect=Exception("connection refused")):
            with pytest.raises(MinIOConnectionError):
                MinIOAdapter()
