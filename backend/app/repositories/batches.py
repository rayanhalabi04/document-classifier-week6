import uuid
from typing import Optional

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models import Batch, BatchStatus


class BatchRepository:
    """SQL-only access for the batches table."""

    def __init__(self, session: Session) -> None:
        self.session = session

    def get_by_id(self, batch_id: uuid.UUID) -> Optional[Batch]:
        stmt = select(Batch).where(Batch.id == batch_id)
        return self.session.execute(stmt).scalar_one_or_none()

    def list(
        self,
        status: Optional[BatchStatus] = None,
        limit: int = 50,
        offset: int = 0,
    ) -> list[Batch]:
        stmt = (
            select(Batch).order_by(Batch.created_at.desc()).limit(limit).offset(offset)
        )
        if status is not None:
            stmt = stmt.where(Batch.status == status)
        return list(self.session.execute(stmt).scalars().all())

    def create(self, batch: Batch) -> Batch:
        self.session.add(batch)
        self.session.flush()
        return batch

    def update(self, batch: Batch) -> Batch:
        self.session.flush()
        return batch
