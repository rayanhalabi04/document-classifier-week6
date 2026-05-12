"""Unit tests for the Atmoz SFTP connection and polling adapter."""

from __future__ import annotations

from datetime import datetime
from io import BytesIO
from unittest.mock import Mock, patch

import pytest

from app.infra.sftp import (
    SFTPAdapter,
    SFTPConnectionError,
    SFTPFileError,
    SFTPFileInfo,
    SFTPPermissionError,
)


@pytest.fixture
def mock_transport() -> Mock:
    """Return a mock paramiko.Transport."""
    return Mock()


@pytest.fixture
def mock_sftp() -> Mock:
    """Return a mock paramiko.SFTPClient."""
    return Mock()


@pytest.fixture
def sftp_adapter(mock_transport, mock_sftp) -> SFTPAdapter:
    """Return a connected SFTPAdapter with mocked transport and SFTP session."""
    with (
        patch("paramiko.Transport", return_value=mock_transport),
        patch("paramiko.SFTPClient.from_transport", return_value=mock_sftp),
        patch("paramiko.util.log_to_file"),
    ):
        adapter = SFTPAdapter(
            host="sftp",
            port=22,
            username="vendor",
            password="vendorpass",
        )
        adapter.__enter__()
        yield adapter
        # Clean up to prevent resource warnings
        adapter._sftp = None
        adapter._transport = None


class MockSFTPAttributes:
    """Minimal mock of SFTPAttributes for listdir_attr."""

    def __init__(self, filename, st_size, st_mtime, is_dir=False):
        self.filename = filename
        self.st_size = st_size
        self.st_mtime = st_mtime
        self.st_mode = 0o040755 if is_dir else 0o100644


class TestListFiles:
    """Tests for SFTPAdapter.list_files."""

    def test_returns_empty_list_for_empty_dir(self, sftp_adapter, mock_sftp):
        """Given an empty directory, returns an empty list."""
        mock_sftp.listdir_attr.return_value = []

        result = sftp_adapter.list_files("/home/vendor/drop")

        assert result == []

    def test_returns_file_infos_for_directory_with_files(self, sftp_adapter, mock_sftp):
        """Given a directory with files, returns SFTPFileInfo for each."""
        mock_sftp.listdir_attr.return_value = [
            MockSFTPAttributes("doc1.tiff", 1024, 1715472000.0),
            MockSFTPAttributes("doc2.tiff", 2048, 1715472100.0),
        ]

        result = sftp_adapter.list_files("/home/vendor/drop")

        assert len(result) == 2
        assert result[0].filename == "doc1.tiff"
        assert result[0].remote_path == "/home/vendor/drop/doc1.tiff"
        assert result[0].size_bytes == 1024
        assert result[0].modified_at == datetime.fromtimestamp(1715472000.0)
        assert result[1].filename == "doc2.tiff"
        assert result[1].size_bytes == 2048

    def test_skips_directories_in_listing(self, sftp_adapter, mock_sftp):
        """Given a directory with subdirectories, skips them and only returns files."""
        mock_sftp.listdir_attr.return_value = [
            MockSFTPAttributes("subdir", 4096, 1715472000.0, is_dir=True),
            MockSFTPAttributes("doc.tiff", 1024, 1715472100.0),
        ]

        result = sftp_adapter.list_files("/home/vendor/drop")

        assert len(result) == 1
        assert result[0].filename == "doc.tiff"

    def test_raises_permission_error_on_permission_denied(self, sftp_adapter, mock_sftp):
        """Given a directory without read access, raises SFTPPermissionError."""
        mock_sftp.listdir_attr.side_effect = PermissionError("permission denied")

        with pytest.raises(SFTPPermissionError):
            sftp_adapter.list_files("/home/vendor/drop")

    def test_raises_file_error_on_nonexistent_directory(self, sftp_adapter, mock_sftp):
        """Given a nonexistent directory, raises SFTPFileError."""
        mock_sftp.listdir_attr.side_effect = FileNotFoundError("no such dir")

        with pytest.raises(SFTPFileError):
            sftp_adapter.list_files("/nonexistent")


class TestGetFileMetadata:
    """Tests for SFTPAdapter.get_file_metadata."""

    def test_returns_file_info_from_stat(self, sftp_adapter, mock_sftp):
        """Given a valid file, returns SFTPFileInfo with stat results."""
        mock_attr = Mock()
        mock_attr.st_size = 4096
        mock_attr.st_mtime = 1715472000.0
        mock_sftp.stat.return_value = mock_attr

        result = sftp_adapter.get_file_metadata("/home/vendor/drop/doc.tiff")

        assert result.filename == "doc.tiff"
        assert result.remote_path == "/home/vendor/drop/doc.tiff"
        assert result.size_bytes == 4096
        assert result.modified_at == datetime.fromtimestamp(1715472000.0)

    def test_raises_file_error_on_missing_file(self, sftp_adapter, mock_sftp):
        """Given a nonexistent file, raises SFTPFileError."""
        mock_sftp.stat.side_effect = FileNotFoundError("not found")

        with pytest.raises(SFTPFileError):
            sftp_adapter.get_file_metadata("/home/vendor/drop/missing.tiff")

    def test_raises_permission_error_on_access_denied(self, sftp_adapter, mock_sftp):
        """Given a file without read permission, raises SFTPPermissionError."""
        mock_sftp.stat.side_effect = PermissionError("access denied")

        with pytest.raises(SFTPPermissionError):
            sftp_adapter.get_file_metadata("/home/vendor/drop/restricted.tiff")


class TestReadFileContent:
    """Tests for SFTPAdapter.read_file_content and open_file."""

    def test_reads_full_file_content(self, sftp_adapter, mock_sftp):
        """Given a valid file, returns the full content as bytes."""
        content = b"\x00" * 1024
        mock_sftp.open.return_value = BytesIO(content)

        result = sftp_adapter.read_file_content("/home/vendor/drop/doc.tiff")

        assert result == content

    def test_open_file_returns_binary_stream(self, sftp_adapter, mock_sftp):
        """open_file returns a file-like object for streaming."""
        content = b"test"
        mock_sftp.open.return_value = BytesIO(content)

        fh = sftp_adapter.open_file("/home/vendor/drop/doc.tiff")

        assert fh.read() == content

    def test_raises_file_error_on_missing_file(self, sftp_adapter, mock_sftp):
        """Given a nonexistent file for reading, raises SFTPFileError."""
        mock_sftp.open.side_effect = FileNotFoundError("not found")

        with pytest.raises(SFTPFileError):
            sftp_adapter.read_file_content("/home/vendor/drop/missing.tiff")

    def test_raises_permission_error_on_restricted_file(self, sftp_adapter, mock_sftp):
        """Given a file without read permission, raises SFTPPermissionError."""
        mock_sftp.open.side_effect = PermissionError("access denied")

        with pytest.raises(SFTPPermissionError):
            sftp_adapter.open_file("/home/vendor/drop/restricted.tiff")


class TestSFTPAdapterInit:
    """Tests for SFTPAdapter initialization and connection."""

    def test_context_manager_connects_and_disconnects(self):
        """When used as context manager, transport is properly closed."""
        mock_transport = Mock()
        mock_sftp = Mock()

        with (
            patch("paramiko.Transport", return_value=mock_transport),
            patch("paramiko.SFTPClient.from_transport", return_value=mock_sftp),
            patch("paramiko.util.log_to_file"),
        ):
            adapter = SFTPAdapter(
                host="sftp", port=22, username="vendor", password="pass"
            )
            with adapter:
                assert adapter._transport is mock_transport
                assert adapter._sftp is mock_sftp

            mock_sftp.close.assert_called_once()
            mock_transport.close.assert_called_once()

    def test_raises_connection_error_on_auth_failure(self):
        """Given bad credentials, raises SFTPConnectionError."""
        mock_transport = Mock()
        mock_transport.connect.side_effect = __import__("paramiko").AuthenticationException("auth failed")

        with (
            patch("paramiko.Transport", return_value=mock_transport),
            patch("paramiko.util.log_to_file"),
        ):
            adapter = SFTPAdapter(
                host="sftp", port=22, username="vendor", password="wrong"
            )
            with pytest.raises(SFTPConnectionError):
                adapter.__enter__()

    def test_raises_connection_error_when_used_without_context(self):
        """Using methods outside context manager raises SFTPConnectionError."""
        adapter = SFTPAdapter(
            host="sftp", port=22, username="vendor", password="pass"
        )
        with pytest.raises(SFTPConnectionError, match="context manager"):
            adapter.list_files("/tmp")

    def test_handles_disappeared_file_between_list_and_read(self, sftp_adapter, mock_sftp):
        """File disappearing between list and read raises SFTPFileError."""
        mock_sftp.open.side_effect = FileNotFoundError("vanished")

        with pytest.raises(SFTPFileError):
            sftp_adapter.read_file_content("/home/vendor/drop/vanished.tiff")
