import uuid
from typing import Optional

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models import Document, IngestionStatus


class DocumentRepository:
    """SQL-only access for the documents table."""

    def __init__(self, session: Session) -> None:
        self.session = session

    def get_by_id(self, document_id: uuid.UUID) -> Optional[Document]:
        stmt = select(Document).where(Document.id == document_id)
        return self.session.execute(stmt).scalar_one_or_none()

    def list_by_batch(self, batch_id: uuid.UUID) -> list[Document]:
        stmt = (
            select(Document)
            .where(Document.batch_id == batch_id)
            .order_by(Document.created_at.asc())
        )
        return list(self.session.execute(stmt).scalars().all())

    def find_active_duplicate(
        self, source_checksum: str, source_path: str
    ) -> Optional[Document]:
        """Return an existing non-failed document with the same checksum and path."""
        stmt = select(Document).where(
            Document.source_checksum == source_checksum,
            Document.source_path == source_path,
            Document.ingestion_status != IngestionStatus.failed,
        )
        return self.session.execute(stmt).scalar_one_or_none()

    def create(self, document: Document) -> Document:
        self.session.add(document)
        self.session.flush()
        return document

    def update(self, document: Document) -> Document:
        self.session.flush()
        return document
