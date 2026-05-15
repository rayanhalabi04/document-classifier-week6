"""Shared test fixtures for the document-classifier test suite.

Fixtures cascade into contract/, unit/, repository/, service/, golden/,
and integration/ subdirectories automatically.
"""

from __future__ import annotations

import uuid
from types import SimpleNamespace
from unittest.mock import MagicMock, Mock

import pytest
from fastapi.testclient import TestClient

from app.domain.errors import PermissionDenied
from app.main import app


# ── UUID fixtures ────────────────────────────────────────────────


@pytest.fixture
def user_id() -> uuid.UUID:
    return uuid.uuid4()


@pytest.fixture
def batch_id() -> uuid.UUID:
    return uuid.uuid4()


@pytest.fixture
def document_id() -> uuid.UUID:
    return uuid.uuid4()


@pytest.fixture
def prediction_id() -> uuid.UUID:
    return uuid.uuid4()


@pytest.fixture
def job_id() -> uuid.UUID:
    return uuid.uuid4()


# ── User stubs ───────────────────────────────────────────────────


@pytest.fixture
def active_user(user_id: uuid.UUID) -> SimpleNamespace:
    return SimpleNamespace(
        id=user_id,
        email="user@example.com",
        is_active=True,
        is_verified=True,
    )


@pytest.fixture
def active_admin(user_id: uuid.UUID) -> SimpleNamespace:
    return SimpleNamespace(
        id=user_id,
        email="admin@example.com",
        is_active=True,
        is_verified=True,
    )


# ── Managed TestClient with auto-cleanup ─────────────────────────


@pytest.fixture
def client() -> TestClient:
    try:
        yield TestClient(app)
    finally:
        app.dependency_overrides.clear()


# ── Authorization service stubs ──────────────────────────────────


@pytest.fixture
def allowed_auth() -> Mock:
    auth = Mock()
    auth.require_permission.return_value = None
    return auth


@pytest.fixture
def denied_auth() -> Mock:
    auth = Mock()
    auth.require_permission.side_effect = PermissionDenied("test-denied")
    return auth


# ── Service mock helpers ─────────────────────────────────────────


@pytest.fixture
def mock_service() -> Mock:
    """Returns a generic Mock for use as a service dependency."""
    return Mock()


@pytest.fixture
def mock_session() -> MagicMock:
    """Returns a MagicMock mimicking a SQLAlchemy session."""
    return MagicMock()


# ── Common data helpers ──────────────────────────────────────────


@pytest.fixture
def sample_tiff_bytes() -> bytes:
    """Little-endian TIFF header bytes for use in ingestion tests."""
    return b"\x49\x49\x2a\x00" + b"\x00" * 100
