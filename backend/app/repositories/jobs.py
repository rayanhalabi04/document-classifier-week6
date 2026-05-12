import uuid
from typing import Optional

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models import ClassificationJob, JobStatus


class ClassificationJobRepository:
    """SQL-only access for the classification_jobs table."""

    def __init__(self, session: Session) -> None:
        self.session = session

    def get_by_id(self, job_id: uuid.UUID) -> Optional[ClassificationJob]:
        stmt = select(ClassificationJob).where(ClassificationJob.id == job_id)
        return self.session.execute(stmt).scalar_one_or_none()

    def get_by_rq_job_id(self, rq_job_id: str) -> Optional[ClassificationJob]:
        stmt = select(ClassificationJob).where(
            ClassificationJob.rq_job_id == rq_job_id
        )
        return self.session.execute(stmt).scalar_one_or_none()

    def list_by_document(self, document_id: uuid.UUID) -> list[ClassificationJob]:
        stmt = (
            select(ClassificationJob)
            .where(ClassificationJob.document_id == document_id)
            .order_by(ClassificationJob.enqueued_at.asc())
        )
        return list(self.session.execute(stmt).scalars().all())

    def get_active_by_document(
        self, document_id: uuid.UUID
    ) -> Optional[ClassificationJob]:
        """Return the in-progress job for a document, if any."""
        stmt = select(ClassificationJob).where(
            ClassificationJob.document_id == document_id,
            ClassificationJob.status.in_([JobStatus.queued, JobStatus.running]),
        )
        return self.session.execute(stmt).scalar_one_or_none()

    def create(self, job: ClassificationJob) -> ClassificationJob:
        self.session.add(job)
        self.session.flush()
        return job

    def update(self, job: ClassificationJob) -> ClassificationJob:
        self.session.flush()
        return job
