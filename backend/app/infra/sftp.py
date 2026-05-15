"""Atmoz SFTP connection and polling adapter."""

from __future__ import annotations

import socket
from dataclasses import dataclass
from datetime import datetime
from typing import BinaryIO

import paramiko

from app.config import settings


class SFTPError(Exception):
    """Base exception for SFTP adapter operations."""


class SFTPConnectionError(SFTPError):
    """Raised when connection or authentication to the SFTP server fails."""


class SFTPPermissionError(SFTPError):
    """Raised when a directory or file is not accessible due to permissions."""


class SFTPFileError(SFTPError):
    """Raised when a file operation fails (e.g. file not found or read error)."""


@dataclass
class SFTPFileInfo:
    """Metadata for a file on the SFTP server.

    Attributes:
        filename: The file name without directory.
        remote_path: The full path on the remote server.
        size_bytes: File size in bytes.
        modified_at: Last modification timestamp.
    """

    filename: str
    remote_path: str
    size_bytes: int
    modified_at: datetime


class SFTPAdapter:
    """Adapter for listing, inspecting, and reading files from Atmoz SFTP.

    Uses Paramiko for SSH/SFTP transport. Supports streaming reads
    and reports connection, permission, and file-level failures clearly.
    """

    def __init__(
        self,
        host: str,
        port: int,
        username: str,
        password: str,
    ):
        """Initialize the SFTP adapter with connection parameters.

        Args:
            host: SFTP server hostname or IP.
            port: SSH port.
            username: SFTP username.
            password: SFTP password.
        """
        self._host = host
        self._port = port
        self._username = username
        self._password = password
        self._transport: paramiko.Transport | None = None
        self._sftp: paramiko.SFTPClient | None = None

    def __enter__(self) -> SFTPAdapter:
        """Open the SSH transport and SFTP session.

        Returns:
            The connected SFTPAdapter instance.

        Raises:
            SFTPConnectionError: On authentication or transport failure.
        """
        try:
            sock = socket.create_connection(
                (self._host, self._port),
                timeout=settings.http_connect_timeout,
            )
            self._transport = paramiko.Transport(sock)
        except Exception as exc:
            raise SFTPConnectionError(
                f"Failed to connect to {self._host}:{self._port}: {exc}"
            ) from exc

        try:
            self._transport.connect(
                username=self._username,
                password=self._password,
            )
        except paramiko.AuthenticationException as exc:
            self._transport.close()
            raise SFTPConnectionError(
                f"Authentication failed for user '{self._username}' on {self._host}:{self._port}"
            ) from exc
        except paramiko.SSHException as exc:
            self._transport.close()
            raise SFTPConnectionError(
                f"SSH transport error connecting to {self._host}:{self._port}: {exc}"
            ) from exc

        try:
            self._sftp = paramiko.SFTPClient.from_transport(self._transport)
        except paramiko.SSHException as exc:
            self._transport.close()
            raise SFTPConnectionError(
                f"Failed to open SFTP session on {self._host}:{self._port}: {exc}"
            ) from exc

        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        """Close the SFTP session and SSH transport."""
        if self._sftp is not None:
            self._sftp.close()
            self._sftp = None
        if self._transport is not None:
            self._transport.close()
            self._transport = None
        return False

    def list_files(self, remote_dir: str) -> list[SFTPFileInfo]:
        """List all files in a remote directory.

        Args:
            remote_dir: Path to the directory on the SFTP server.

        Returns:
            List of SFTPFileInfo for each file. Empty list if the directory
            is empty. Directories are skipped.

        Raises:
            SFTPPermissionError: If the directory is not readable.
            SFTPFileError: If the directory does not exist.
            SFTPConnectionError: If the SFTP session is not connected.
        """
        self._ensure_connected()
        try:
            entries = self._sftp.listdir_attr(remote_dir)
        except PermissionError:
            raise SFTPPermissionError(
                f"Permission denied listing directory '{remote_dir}'"
            )
        except FileNotFoundError:
            raise SFTPFileError(f"Directory not found: '{remote_dir}'")
        except OSError as exc:
            raise SFTPFileError(
                f"Failed to list directory '{remote_dir}': {exc}"
            ) from exc

        results: list[SFTPFileInfo] = []
        for entry in entries:
            if entry.st_mode is not None and not self._is_regular_file(entry.st_mode):
                continue
            remote_path = f"{remote_dir.rstrip('/')}/{entry.filename}"
            results.append(
                SFTPFileInfo(
                    filename=entry.filename,
                    remote_path=remote_path,
                    size_bytes=entry.st_size or 0,
                    modified_at=datetime.fromtimestamp(entry.st_mtime or 0),
                )
            )
        return results

    def get_file_metadata(self, remote_path: str) -> SFTPFileInfo:
        """Get size and modification time for a single file.

        Args:
            remote_path: Full path to the file on the SFTP server.

        Returns:
            SFTPFileInfo with file metadata.

        Raises:
            SFTPFileError: If the file does not exist or cannot be statted.
            SFTPConnectionError: If the SFTP session is not connected.
        """
        self._ensure_connected()
        try:
            attr = self._sftp.stat(remote_path)
        except FileNotFoundError:
            raise SFTPFileError(f"File not found: '{remote_path}'")
        except PermissionError:
            raise SFTPPermissionError(
                f"Permission denied accessing file: '{remote_path}'"
            )
        except OSError as exc:
            raise SFTPFileError(f"Failed to stat file '{remote_path}': {exc}") from exc

        filename = remote_path.rsplit("/", 1)[-1]
        return SFTPFileInfo(
            filename=filename,
            remote_path=remote_path,
            size_bytes=attr.st_size or 0,
            modified_at=datetime.fromtimestamp(attr.st_mtime or 0),
        )

    def open_file(self, remote_path: str) -> BinaryIO:
        """Open a remote file for streaming read.

        Returns a file-like object for lazy reading. The caller is
        responsible for closing the handle.

        Args:
            remote_path: Full path to the file on the SFTP server.

        Returns:
            A binary file-like object for reading.

        Raises:
            SFTPFileError: If the file cannot be opened.
            SFTPConnectionError: If the SFTP session is not connected.
        """
        self._ensure_connected()
        try:
            return self._sftp.open(remote_path, "rb")
        except FileNotFoundError:
            raise SFTPFileError(f"File not found: '{remote_path}'")
        except PermissionError:
            raise SFTPPermissionError(
                f"Permission denied reading file: '{remote_path}'"
            )
        except OSError as exc:
            raise SFTPFileError(f"Failed to open file '{remote_path}': {exc}") from exc

    def read_file_content(self, remote_path: str) -> bytes:
        """Read the full content of a remote file.

        Convenience wrapper around open_file for non-streaming use.

        Args:
            remote_path: Full path to the file on the SFTP server.

        Returns:
            The full file content as bytes.

        Raises:
            SFTPFileError: If the file cannot be read.
        """
        fh = self.open_file(remote_path)
        try:
            return fh.read()
        finally:
            fh.close()

    def _ensure_connected(self) -> None:
        """Verify the SFTP session is active.

        Raises:
            SFTPConnectionError: If no active SFTP session exists.
        """
        if self._sftp is None:
            raise SFTPConnectionError(
                "SFTP session not connected. Use the adapter as a context manager."
            )

    @staticmethod
    def _is_regular_file(mode: int) -> bool:
        """Check if a stat mode represents a regular file."""
        import stat

        return stat.S_ISREG(mode)


def check_connection() -> None:
    """Verify SFTP connection and drop directory readability.

    Module-level function called by ingestion worker startup validation.
    Connects, lists the drop directory, and confirms it is accessible.
    """
    from app.config import settings

    with SFTPAdapter(
        settings.sftp_host,
        settings.sftp_port,
        settings.sftp_user,
        settings.sftp_password,
    ) as sftp:
        sftp.list_files(settings.sftp_drop_dir)
