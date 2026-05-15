"""Unit tests for app/infra/redis.py (T031)."""

from unittest.mock import MagicMock, patch

from app.infra.redis import check_redis_health, get_async_redis_client, get_redis_client


class TestGetRedisClient:
    def test_returns_sync_client(self):
        get_redis_client.cache_clear()
        with patch("app.infra.redis.Redis.from_url") as mock:
            mock.return_value = MagicMock()
            get_redis_client()
            mock.assert_called_once()

    def test_uses_redis_url_env_var(self, monkeypatch):
        get_redis_client.cache_clear()
        with patch("app.infra.redis.settings") as mock_settings:
            mock_settings.redis_url = "redis://custom:6380/1"
            with patch("app.infra.redis.Redis.from_url") as mock:
                mock.return_value = MagicMock()
                get_redis_client()
                assert "redis://custom:6380/1" in mock.call_args[0][0]

    def test_uses_default_url_when_env_unset(self, monkeypatch):
        get_redis_client.cache_clear()
        with patch("app.infra.redis.settings") as mock_settings:
            mock_settings.redis_url = "redis://redis:6379/0"
            with patch("app.infra.redis.Redis.from_url") as mock:
                mock.return_value = MagicMock()
                get_redis_client()
                assert "redis://redis:6379/0" in mock.call_args[0][0]

    def test_decode_responses_is_false(self, monkeypatch):
        get_redis_client.cache_clear()
        with patch("app.infra.redis.settings") as mock_settings:
            mock_settings.redis_url = "redis://redis:6379/0"
            with patch("app.infra.redis.Redis.from_url") as mock:
                mock.return_value = MagicMock()
                get_redis_client()
                assert mock.call_args[1].get("decode_responses") is False


class TestGetAsyncRedisClient:
    def test_returns_async_client(self):
        get_async_redis_client.cache_clear()
        with patch("app.infra.redis.aioredis.Redis.from_url") as mock:
            mock.return_value = MagicMock()
            get_async_redis_client()
            mock.assert_called_once()

    def test_decode_responses_is_true(self, monkeypatch):
        get_async_redis_client.cache_clear()
        with patch("app.infra.redis.settings") as mock_settings:
            mock_settings.redis_url = "redis://redis:6379/0"
            with patch("app.infra.redis.aioredis.Redis.from_url") as mock:
                mock.return_value = MagicMock()
                get_async_redis_client()
                assert mock.call_args[1].get("decode_responses") is True


class TestCheckRedisHealth:
    def test_calls_ping(self):
        mock_client = MagicMock()
        with patch("app.infra.redis.get_redis_client", return_value=mock_client):
            check_redis_health()
            mock_client.ping.assert_called_once()
