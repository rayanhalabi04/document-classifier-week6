import uuid
from typing import Optional

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models import ModelMetadata


class ModelMetadataRepository:
    """SQL-only access for the model_metadata table."""

    def __init__(self, session: Session) -> None:
        self.session = session

    def get_by_id(self, metadata_id: uuid.UUID) -> Optional[ModelMetadata]:
        stmt = select(ModelMetadata).where(ModelMetadata.id == metadata_id)
        return self.session.execute(stmt).scalar_one_or_none()

    def get_latest(self) -> Optional[ModelMetadata]:
        """Return the most recently registered model metadata record."""
        stmt = (
            select(ModelMetadata)
            .order_by(ModelMetadata.created_at.desc())
            .limit(1)
        )
        return self.session.execute(stmt).scalar_one_or_none()

    def get_by_classifier_checksum(self, checksum: str) -> Optional[ModelMetadata]:
        """Return metadata for an already-registered classifier file."""
        stmt = select(ModelMetadata).where(ModelMetadata.classifier_sha256 == checksum)
        return self.session.execute(stmt).scalar_one_or_none()

    def create(self, metadata: ModelMetadata) -> ModelMetadata:
        self.session.add(metadata)
        self.session.flush()
        return metadata
