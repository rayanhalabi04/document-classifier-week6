"""Unit tests for DocumentRepository."""

import uuid
from unittest.mock import MagicMock

import pytest

from app.db.models import Document, IngestionStatus
from app.repositories.documents import DocumentRepository


class TestGetById:
    def test_returns_document_when_found(self, mock_session, sample_document):
        mock_session.execute.return_value.scalar_one_or_none.return_value = (
            sample_document
        )
        repo = DocumentRepository(mock_session)

        result = repo.get_by_id(sample_document.id)

        assert result is sample_document

    def test_returns_none_when_not_found(self, mock_session):
        mock_session.execute.return_value.scalar_one_or_none.return_value = None
        repo = DocumentRepository(mock_session)

        result = repo.get_by_id(uuid.uuid4())

        assert result is None


class TestListByBatch:
    def test_returns_documents_for_batch(self, mock_session, sample_document, batch_id):
        mock_session.execute.return_value.scalars.return_value.all.return_value = [
            sample_document
        ]
        repo = DocumentRepository(mock_session)

        result = repo.list_by_batch(batch_id)

        assert result == [sample_document]

    def test_returns_empty_list_when_no_documents(self, mock_session, batch_id):
        mock_session.execute.return_value.scalars.return_value.all.return_value = []
        repo = DocumentRepository(mock_session)

        result = repo.list_by_batch(batch_id)

        assert result == []


class TestFindActiveDuplicate:
    def test_returns_existing_document_when_duplicate_found(
        self, mock_session, sample_document
    ):
        mock_session.execute.return_value.scalar_one_or_none.return_value = (
            sample_document
        )
        repo = DocumentRepository(mock_session)

        result = repo.find_active_duplicate(
            sample_document.source_checksum, sample_document.source_path
        )

        assert result is sample_document

    def test_returns_none_when_no_duplicate(self, mock_session):
        mock_session.execute.return_value.scalar_one_or_none.return_value = None
        repo = DocumentRepository(mock_session)

        result = repo.find_active_duplicate("deadbeef", "/vendor/new.tif")

        assert result is None


class TestCreate:
    def test_adds_document_to_session_and_flushes(self, mock_session):
        doc = MagicMock(spec=Document)
        repo = DocumentRepository(mock_session)

        result = repo.create(doc)

        mock_session.add.assert_called_once_with(doc)
        mock_session.flush.assert_called_once()
        assert result is doc


class TestUpdate:
    def test_flushes_session_and_returns_document(self, mock_session, sample_document):
        repo = DocumentRepository(mock_session)

        result = repo.update(sample_document)

        mock_session.flush.assert_called_once()
        assert result is sample_document
