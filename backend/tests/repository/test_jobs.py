"""Unit tests for ClassificationJobRepository."""

import uuid
from unittest.mock import MagicMock

import pytest

from app.db.models import ClassificationJob, JobStatus
from app.repositories.jobs import ClassificationJobRepository


class TestGetById:
    def test_returns_job_when_found(self, mock_session, sample_job):
        mock_session.execute.return_value.scalar_one_or_none.return_value = sample_job
        repo = ClassificationJobRepository(mock_session)

        result = repo.get_by_id(sample_job.id)

        assert result is sample_job

    def test_returns_none_when_not_found(self, mock_session):
        mock_session.execute.return_value.scalar_one_or_none.return_value = None
        repo = ClassificationJobRepository(mock_session)

        result = repo.get_by_id(uuid.uuid4())

        assert result is None


class TestGetByRqJobId:
    def test_returns_job_when_found(self, mock_session, sample_job):
        mock_session.execute.return_value.scalar_one_or_none.return_value = sample_job
        repo = ClassificationJobRepository(mock_session)

        result = repo.get_by_rq_job_id("rq-abc")

        assert result is sample_job

    def test_returns_none_when_not_found(self, mock_session):
        mock_session.execute.return_value.scalar_one_or_none.return_value = None
        repo = ClassificationJobRepository(mock_session)

        result = repo.get_by_rq_job_id("nonexistent-rq-id")

        assert result is None


class TestListByDocument:
    def test_returns_jobs_for_document(self, mock_session, sample_job, document_id):
        mock_session.execute.return_value.scalars.return_value.all.return_value = [sample_job]
        repo = ClassificationJobRepository(mock_session)

        result = repo.list_by_document(document_id)

        assert result == [sample_job]

    def test_returns_empty_list_when_none(self, mock_session, document_id):
        mock_session.execute.return_value.scalars.return_value.all.return_value = []
        repo = ClassificationJobRepository(mock_session)

        result = repo.list_by_document(document_id)

        assert result == []


class TestGetActiveByDocument:
    def test_returns_active_job_when_found(self, mock_session, sample_job, document_id):
        mock_session.execute.return_value.scalar_one_or_none.return_value = sample_job
        repo = ClassificationJobRepository(mock_session)

        result = repo.get_active_by_document(document_id)

        assert result is sample_job

    def test_returns_none_when_no_active_job(self, mock_session, document_id):
        mock_session.execute.return_value.scalar_one_or_none.return_value = None
        repo = ClassificationJobRepository(mock_session)

        result = repo.get_active_by_document(document_id)

        assert result is None


class TestCreate:
    def test_adds_job_to_session_and_flushes(self, mock_session):
        job = MagicMock(spec=ClassificationJob)
        repo = ClassificationJobRepository(mock_session)

        result = repo.create(job)

        mock_session.add.assert_called_once_with(job)
        mock_session.flush.assert_called_once()
        assert result is job


class TestUpdate:
    def test_flushes_session_and_returns_job(self, mock_session, sample_job):
        repo = ClassificationJobRepository(mock_session)

        result = repo.update(sample_job)

        mock_session.flush.assert_called_once()
        assert result is sample_job
