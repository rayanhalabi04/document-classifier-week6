"""Unit tests for BatchRepository."""

import uuid
from unittest.mock import MagicMock

import pytest

from app.db.models import Batch, BatchStatus
from app.repositories.batches import BatchRepository


class TestGetById:
    def test_returns_batch_when_found(self, mock_session, sample_batch):
        mock_session.execute.return_value.scalar_one_or_none.return_value = sample_batch
        repo = BatchRepository(mock_session)

        result = repo.get_by_id(sample_batch.id)

        assert result is sample_batch

    def test_returns_none_when_not_found(self, mock_session):
        mock_session.execute.return_value.scalar_one_or_none.return_value = None
        repo = BatchRepository(mock_session)

        result = repo.get_by_id(uuid.uuid4())

        assert result is None


class TestList:
    def test_returns_all_batches_without_filter(self, mock_session, sample_batch):
        mock_session.execute.return_value.scalars.return_value.all.return_value = [
            sample_batch
        ]
        repo = BatchRepository(mock_session)

        result = repo.list()

        assert result == [sample_batch]

    def test_returns_empty_list_when_none(self, mock_session):
        mock_session.execute.return_value.scalars.return_value.all.return_value = []
        repo = BatchRepository(mock_session)

        result = repo.list()

        assert result == []

    def test_accepts_status_filter(self, mock_session, sample_batch):
        mock_session.execute.return_value.scalars.return_value.all.return_value = [
            sample_batch
        ]
        repo = BatchRepository(mock_session)

        result = repo.list(status=BatchStatus.processing)

        assert result == [sample_batch]

    def test_accepts_limit_and_offset(self, mock_session):
        mock_session.execute.return_value.scalars.return_value.all.return_value = []
        repo = BatchRepository(mock_session)

        result = repo.list(limit=10, offset=5)

        assert result == []


class TestCreate:
    def test_adds_batch_to_session_and_flushes(self, mock_session):
        batch = MagicMock(spec=Batch)
        repo = BatchRepository(mock_session)

        result = repo.create(batch)

        mock_session.add.assert_called_once_with(batch)
        mock_session.flush.assert_called_once()
        assert result is batch


class TestUpdate:
    def test_flushes_session_and_returns_batch(self, mock_session, sample_batch):
        repo = BatchRepository(mock_session)

        result = repo.update(sample_batch)

        mock_session.flush.assert_called_once()
        assert result is sample_batch
