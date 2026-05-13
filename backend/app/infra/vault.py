"""HashCorp Vault dev mode KV v2 secrets adapter."""

from __future__ import annotations

import os

import hvac


class VaultError(Exception):
    """Base exception for Vault adapter operations."""


class VaultConnectionError(VaultError):
    """Raised when the Vault server is unreachable or authentication fails."""


class VaultSecretNotFound(VaultError):
    """Raised when a secret path does not exist in Vault KV v2."""


class VaultKeyNotFound(VaultError):
    """Raised when a requested key does not exist within a secret."""


REQUIRED_SECRETS: dict[str, set[str]] = {
    "jwt": {"secret"},
    "postgres": {"user", "password", "db"},
    "minio": {"access_key", "secret_key"},
    "sftp": {"user", "password", "host", "port"},
    "redis": {"url"},
}


class VaultAdapter:
    """Adapter for reading secrets from HashiCorp Vault dev mode KV v2.

    Reads required secrets for JWT, SFTP, MinIO, Postgres, and Redis.
    Provides startup validation that reports which keys are missing.
    """

    def __init__(self, url: str | None = None, token: str | None = None):
        """Initialize the Vault adapter.

        Args:
            url: Vault server URL. Falls back to VAULT_ADDR env var.
            token: Vault authentication token. Falls back to VAULT_TOKEN env var.

        Raises:
            VaultConnectionError: If the client cannot authenticate.
        """
        self._url = url or os.environ.get("VAULT_ADDR", "http://localhost:8200")
        self._token = token or os.environ.get("VAULT_TOKEN", "")
        if not self._token:
            raise VaultConnectionError(
                "Vault token not provided and VAULT_TOKEN env var not set"
            )

        try:
            self._client = hvac.Client(url=self._url, token=self._token)
        except Exception as exc:
            raise VaultConnectionError(
                f"Failed to create Vault client for {self._url}: {exc}"
            ) from exc

        try:
            authenticated = self._client.is_authenticated()
        except Exception as exc:
            raise VaultConnectionError(
                f"Failed to verify Vault authentication at {self._url}: {exc}"
            ) from exc

        if not authenticated:
            raise VaultConnectionError(f"Vault authentication failed at {self._url}")

    def read_secret(self, path: str, key: str) -> str:
        """Read a single secret value from KV v2 by path and key.

        Args:
            path: KV v2 secret path (e.g. 'jwt').
            key: Key within the secret data dict (e.g. 'secret').

        Returns:
            The secret value as a string.

        Raises:
            VaultSecretNotFound: If the secret path does not exist.
            VaultKeyNotFound: If the key does not exist within the secret.
            VaultConnectionError: If the Vault request fails.
        """
        try:
            response = self._client.secrets.kv.v2.read_secret_version(
                path=path,
                raise_on_deleted_version=True,
            )
        except hvac.exceptions.InvalidPath as exc:
            raise VaultSecretNotFound(
                f"Secret path '{path}' not found in Vault"
            ) from exc
        except hvac.exceptions.VaultError as exc:
            raise VaultConnectionError(
                f"Vault request failed for path '{path}': {exc}"
            ) from exc

        data = response.get("data", {}).get("data", {})
        if key not in data:
            raise VaultKeyNotFound(f"Key '{key}' not found in secret path '{path}'")

        return str(data[key])

    def validate_required_secrets(self) -> dict[str, dict[str, bool]]:
        """Validate that all required secret paths and keys exist in Vault.

        Returns:
            Nested dict mapping each secret path to a dict of key->bool.
            True means the secret key was found; False means it is missing.
        """
        results: dict[str, dict[str, bool]] = {}

        for path, keys in REQUIRED_SECRETS.items():
            results[path] = {}
            for key in keys:
                try:
                    self.read_secret(path, key)
                    results[path][key] = True
                except (VaultSecretNotFound, VaultKeyNotFound, VaultConnectionError):
                    results[path][key] = False

        return results


def validate_required_secrets() -> None:
    """Verify all required Vault secrets exist.

    Module-level wrapper called by startup validation.
    Raises VaultConnectionError if any required secret is missing.
    """
    adapter = VaultAdapter()
    results = adapter.validate_required_secrets()
    missing = [
        f"{path}:{key}"
        for path, keys in results.items()
        for key, ok in keys.items()
        if not ok
    ]
    if missing:
        raise VaultConnectionError(f"Missing Vault secrets: {', '.join(missing)}")
