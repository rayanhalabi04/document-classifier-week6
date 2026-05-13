"""Unit tests for AuditEventRepository."""

import uuid
from unittest.mock import MagicMock

import pytest

from app.db.models import AuditEvent
from app.repositories.audit_events import AuditEventRepository


class TestCreate:
    def test_adds_event_to_session_and_flushes(self, mock_session):
        event = MagicMock(spec=AuditEvent)
        repo = AuditEventRepository(mock_session)

        result = repo.create(event)

        mock_session.add.assert_called_once_with(event)
        mock_session.flush.assert_called_once()
        assert result is event


class TestGetById:
    def test_returns_event_when_found(self, mock_session):
        event = MagicMock(spec=AuditEvent)
        event.id = uuid.uuid4()
        mock_session.execute.return_value.scalar_one_or_none.return_value = event
        repo = AuditEventRepository(mock_session)

        result = repo.get_by_id(event.id)

        assert result is event

    def test_returns_none_when_not_found(self, mock_session):
        mock_session.execute.return_value.scalar_one_or_none.return_value = None
        repo = AuditEventRepository(mock_session)

        result = repo.get_by_id(uuid.uuid4())

        assert result is None


class TestList:
    def test_returns_events_without_filters(self, mock_session):
        event = MagicMock(spec=AuditEvent)
        mock_session.execute.return_value.scalars.return_value.all.return_value = [
            event
        ]
        repo = AuditEventRepository(mock_session)

        result = repo.list()

        assert result == [event]

    def test_returns_empty_list_when_none(self, mock_session):
        mock_session.execute.return_value.scalars.return_value.all.return_value = []
        repo = AuditEventRepository(mock_session)

        result = repo.list()

        assert result == []

    def test_accepts_actor_filter(self, mock_session):
        mock_session.execute.return_value.scalars.return_value.all.return_value = []
        repo = AuditEventRepository(mock_session)

        result = repo.list(actor_user_id=uuid.uuid4())

        assert result == []

    def test_accepts_action_filter(self, mock_session):
        event = MagicMock(spec=AuditEvent)
        mock_session.execute.return_value.scalars.return_value.all.return_value = [
            event
        ]
        repo = AuditEventRepository(mock_session)

        result = repo.list(action="document.ingested")

        assert result == [event]

    def test_accepts_target_type_and_id_filters(self, mock_session):
        mock_session.execute.return_value.scalars.return_value.all.return_value = []
        repo = AuditEventRepository(mock_session)

        result = repo.list(target_type="document", target_id=str(uuid.uuid4()))

        assert result == []

    def test_accepts_limit_and_offset(self, mock_session):
        mock_session.execute.return_value.scalars.return_value.all.return_value = []
        repo = AuditEventRepository(mock_session)

        result = repo.list(limit=25, offset=10)

        assert result == []
