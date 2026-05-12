"""Unit tests for the Vault dev mode KV v2 adapter."""

from __future__ import annotations

import os
from unittest.mock import MagicMock, Mock, patch

import hvac
import pytest

from app.infra.vault import (
    REQUIRED_SECRETS,
    VaultAdapter,
    VaultConnectionError,
    VaultKeyNotFound,
    VaultSecretNotFound,
)


@pytest.fixture
def mock_hvac_client() -> Mock:
    """Return a mock hvac.Client that is authenticated."""
    client = Mock()
    client.is_authenticated.return_value = True
    return client


@pytest.fixture
def vault_adapter(mock_hvac_client: Mock) -> VaultAdapter:
    """Return a VaultAdapter with a mock hvac client."""
    with patch("app.infra.vault.hvac.Client", return_value=mock_hvac_client):
        return VaultAdapter(url="http://vault:8200", token="test-token")


class TestReadSecret:
    """Tests for VaultAdapter.read_secret."""

    def test_reads_secret_value_for_valid_path_and_key(self, vault_adapter, mock_hvac_client):
        """Given a valid path and key, returns the secret value."""
        mock_hvac_client.secrets.kv.v2.read_secret_version.return_value = {
            "data": {
                "data": {
                    "secret": "my-jwt-key",
                }
            }
        }

        result = vault_adapter.read_secret("jwt", "secret")

        assert result == "my-jwt-key"
        mock_hvac_client.secrets.kv.v2.read_secret_version.assert_called_once_with(
            path="jwt", raise_on_deleted_version=True
        )

    def test_raises_vault_secret_not_found_for_missing_path(self, vault_adapter, mock_hvac_client):
        """Given a path that does not exist, raises VaultSecretNotFound."""
        mock_hvac_client.secrets.kv.v2.read_secret_version.side_effect = (
            hvac.exceptions.InvalidPath("secret path not found")
        )

        with pytest.raises(VaultSecretNotFound) as exc_info:
            vault_adapter.read_secret("nonexistent", "secret")
        assert "nonexistent" in str(exc_info.value)

    def test_raises_vault_key_not_found_for_missing_key(self, vault_adapter, mock_hvac_client):
        """Given a path that exists but key is missing, raises VaultKeyNotFound."""
        mock_hvac_client.secrets.kv.v2.read_secret_version.return_value = {
            "data": {
                "data": {
                    "other_key": "value",
                }
            }
        }

        with pytest.raises(VaultKeyNotFound) as exc_info:
            vault_adapter.read_secret("jwt", "secret")
        assert "secret" in str(exc_info.value)
        assert "jwt" in str(exc_info.value)

    def test_raises_vault_connection_error_on_vault_error(self, vault_adapter, mock_hvac_client):
        """Given a VaultError during read, raises VaultConnectionError."""
        mock_hvac_client.secrets.kv.v2.read_secret_version.side_effect = (
            hvac.exceptions.VaultError("vault is sealed")
        )

        with pytest.raises(VaultConnectionError):
            vault_adapter.read_secret("jwt", "secret")

    def test_reads_nested_secret_structure(self, vault_adapter, mock_hvac_client):
        """Given a multi-key secret, reads the correct key."""
        mock_hvac_client.secrets.kv.v2.read_secret_version.return_value = {
            "data": {
                "data": {
                    "user": "pguser",
                    "password": "pgpass",
                    "db": "mydb",
                }
            }
        }

        assert vault_adapter.read_secret("postgres", "user") == "pguser"
        assert vault_adapter.read_secret("postgres", "password") == "pgpass"
        assert vault_adapter.read_secret("postgres", "db") == "mydb"


class TestValidateRequiredSecrets:
    """Tests for VaultAdapter.validate_required_secrets."""

    def test_returns_all_true_when_all_secrets_present(self, vault_adapter, mock_hvac_client):
        """Given all required secrets exist, all keys return True."""
        def read_secret_side_effect(path, key):
            return "secret-value"

        mock_hvac_client.secrets.kv.v2.read_secret_version.side_effect = (
            lambda path, raise_on_deleted_version=None: {
                "data": {"data": {k: "val" for k in REQUIRED_SECRETS.get(path, set())}}
            }
        )

        results = vault_adapter.validate_required_secrets()

        for path, keys in results.items():
            for key, present in keys.items():
                assert present is True, f"{path}:{key} expected True"

    def test_flags_missing_key_as_false(self, vault_adapter, mock_hvac_client):
        """Given a missing key within a path, only that key is False."""
        def read_side_effect(path, key):
            if path == "jwt" and key == "secret":
                raise VaultKeyNotFound("missing")
            return {
                "data": {"data": {key: "val"}}
            }

        mock_hvac_client.secrets.kv.v2.read_secret_version.side_effect = (
            lambda path, raise_on_deleted: read_side_effect(path, "dummy")
        )

        # Override read_secret to simulate partial failure
        original_read = vault_adapter.read_secret
        def mock_read(path, key):
            if path == "jwt" and key == "secret":
                raise VaultKeyNotFound("missing")
            return {
                "data": {"data": {
                    "user": "u", "password": "p", "db": "d",
                    "access_key": "a", "secret_key": "s",
                    "host": "h", "port": "22",
                    "url": "u",
                }}
            }.get("data", {}).get("data", {}).get(key, "val")

        vault_adapter.read_secret = mock_read

        results = vault_adapter.validate_required_secrets()

        assert results["jwt"]["secret"] is False
        # All other keys should be True
        for path in ("postgres", "minio", "sftp", "redis"):
            for key in results[path]:
                assert results[path][key] is True, f"{path}:{key} expected True"

    def test_flags_missing_path_as_false_for_all_keys(self, vault_adapter):
        """Given an entire path is missing, all its keys are False."""
        def mock_read(path, key):
            if path == "postgres":
                raise VaultSecretNotFound(f"path {path} not found")
            return "val"

        vault_adapter.read_secret = mock_read
        results = vault_adapter.validate_required_secrets()

        for key in ("user", "password", "db"):
            assert results["postgres"][key] is False

    def test_flags_connection_failure_as_false(self, vault_adapter):
        """Given Vault is unreachable, all keys are marked False."""
        def mock_read(path, key):
            raise VaultConnectionError("unreachable")

        vault_adapter.read_secret = mock_read
        results = vault_adapter.validate_required_secrets()

        for path in results:
            for present in results[path].values():
                assert present is False


class TestVaultAdapterInit:
    """Tests for VaultAdapter initialization."""

    def test_raises_vault_connection_error_when_no_token(self):
        """Raises VaultConnectionError when no token is provided and env var unset."""
        with patch.dict(os.environ, {}, clear=True):
            with patch("app.infra.vault.hvac.Client"):
                with pytest.raises(VaultConnectionError, match="token"):
                    VaultAdapter(url="http://vault:8200")

    def test_raises_connection_error_when_client_not_authenticated(self, mock_hvac_client):
        """Raises VaultConnectionError when the client is not authenticated."""
        mock_hvac_client.is_authenticated.return_value = False

        with patch("app.infra.vault.hvac.Client", return_value=mock_hvac_client):
            with pytest.raises(VaultConnectionError, match="authentication failed"):
                VaultAdapter(url="http://vault:8200", token="bad-token")

    def test_uses_env_vars_as_fallbacks(self, mock_hvac_client):
        """Uses VAULT_ADDR and VAULT_TOKEN env vars when constructor args not provided."""
        with patch.dict(os.environ, {"VAULT_ADDR": "http://custom:8200", "VAULT_TOKEN": "env-token"}):
            with patch("app.infra.vault.hvac.Client", return_value=mock_hvac_client) as mock_client_cls:
                VaultAdapter()
                call_kwargs = mock_client_cls.call_args.kwargs
                assert call_kwargs["url"] == "http://custom:8200"
                assert call_kwargs["token"] == "env-token"
