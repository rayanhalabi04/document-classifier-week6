import enum
import uuid
from datetime import datetime
from typing import List, Optional

from fastapi_users.db import SQLAlchemyBaseUserTableUUID
from sqlalchemy import (
    Boolean,
    DateTime,
    Enum as SAEnum,
    Float,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    func,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


class Base(DeclarativeBase):
    pass


class BatchStatus(str, enum.Enum):
    pending = "pending"
    processing = "processing"
    completed = "completed"
    failed = "failed"


class IngestionStatus(str, enum.Enum):
    pending = "pending"
    stored = "stored"
    queued = "queued"
    processing = "processing"
    completed = "completed"
    failed = "failed"


class JobStatus(str, enum.Enum):
    queued = "queued"
    running = "running"
    succeeded = "succeeded"
    retryable_failed = "retryable_failed"
    terminal_failed = "terminal_failed"


class User(SQLAlchemyBaseUserTableUUID, Base):
    """fastapi-users compatible user table with audit timestamps."""

    __tablename__ = "users"

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )
    last_login_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True)
    )

    role_assignments: Mapped[List["RoleAssignment"]] = relationship(
        "RoleAssignment",
        back_populates="user",
        foreign_keys="[RoleAssignment.user_id]",
    )


class RoleAssignment(Base):
    """Active and historical role grants for users."""

    __tablename__ = "role_assignments"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE")
    )
    role: Mapped[str] = mapped_column(String(50))
    assigned_by_user_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id")
    )
    assigned_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    revoked_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))

    user: Mapped["User"] = relationship(
        "User", back_populates="role_assignments", foreign_keys=[user_id]
    )
    assigned_by: Mapped[Optional["User"]] = relationship(
        "User", foreign_keys=[assigned_by_user_id]
    )

    __table_args__ = (
        Index(
            "ix_role_assignments_user_active",
            "user_id",
            "role",
            postgresql_where="revoked_at IS NULL",
        ),
    )


class CasbinRule(Base):
    """Casbin SQLAlchemy adapter policy storage."""

    __tablename__ = "casbin_rule"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    ptype: Mapped[Optional[str]] = mapped_column(String(255))
    v0: Mapped[Optional[str]] = mapped_column(String(255))
    v1: Mapped[Optional[str]] = mapped_column(String(255))
    v2: Mapped[Optional[str]] = mapped_column(String(255))
    v3: Mapped[Optional[str]] = mapped_column(String(255))
    v4: Mapped[Optional[str]] = mapped_column(String(255))
    v5: Mapped[Optional[str]] = mapped_column(String(255))

    def __str__(self) -> str:
        values = [self.ptype, self.v0, self.v1, self.v2, self.v3, self.v4, self.v5]
        return ", ".join(value for value in values if value is not None)


class Batch(Base):
    """Vendor ingestion grouping for a set of scanned documents."""

    __tablename__ = "batches"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    source: Mapped[str] = mapped_column(String(255))
    status: Mapped[BatchStatus] = mapped_column(
        SAEnum(BatchStatus, name="batchstatus"), default=BatchStatus.pending
    )
    document_count: Mapped[int] = mapped_column(Integer, default=0)
    reviewable_count: Mapped[int] = mapped_column(Integer, default=0)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )
    completed_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))

    documents: Mapped[List["Document"]] = relationship(
        "Document", back_populates="batch"
    )

    __table_args__ = (
        Index("ix_batches_status", "status"),
        Index("ix_batches_created_at", "created_at"),
    )


class Document(Base):
    """Source TIFF metadata and original object storage location."""

    __tablename__ = "documents"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    batch_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("batches.id")
    )
    source_path: Mapped[str] = mapped_column(String(1024))
    source_filename: Mapped[str] = mapped_column(String(512))
    source_size_bytes: Mapped[Optional[int]] = mapped_column(Integer)
    source_checksum: Mapped[Optional[str]] = mapped_column(String(64))
    blob_bucket: Mapped[Optional[str]] = mapped_column(String(255))
    blob_key: Mapped[Optional[str]] = mapped_column(String(1024))
    mime_type: Mapped[Optional[str]] = mapped_column(String(255))
    ingestion_status: Mapped[IngestionStatus] = mapped_column(
        SAEnum(IngestionStatus, name="ingestionstatus"), default=IngestionStatus.pending
    )
    failure_reason: Mapped[Optional[str]] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    batch: Mapped["Batch"] = relationship("Batch", back_populates="documents")
    classification_jobs: Mapped[List["ClassificationJob"]] = relationship(
        "ClassificationJob", back_populates="document"
    )
    predictions: Mapped[List["Prediction"]] = relationship(
        "Prediction", back_populates="document"
    )

    __table_args__ = (
        Index("ix_documents_batch_id", "batch_id"),
        Index("ix_documents_source_checksum", "source_checksum"),
        # Prevents duplicate active ingestion for the same physical file
        Index(
            "ix_documents_source_identity_active",
            "source_checksum",
            "source_path",
            postgresql_where="ingestion_status NOT IN ('failed')",
        ),
    )


class ClassificationJob(Base):
    """Durable view of an RQ job's lifecycle for a document."""

    __tablename__ = "classification_jobs"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    document_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("documents.id")
    )
    rq_job_id: Mapped[Optional[str]] = mapped_column(String(255))
    status: Mapped[JobStatus] = mapped_column(
        SAEnum(JobStatus, name="jobstatus"), default=JobStatus.queued
    )
    attempt_count: Mapped[int] = mapped_column(Integer, default=0)
    last_error: Mapped[Optional[str]] = mapped_column(Text)
    enqueued_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))
    started_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))
    finished_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))

    document: Mapped["Document"] = relationship(
        "Document", back_populates="classification_jobs"
    )

    __table_args__ = (
        Index("ix_classification_jobs_document_id", "document_id"),
        Index("ix_classification_jobs_status", "status"),
    )


class ModelMetadata(Base):
    """Loaded classifier identity and label contract from model_card.json."""

    __tablename__ = "model_metadata"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    model_name: Mapped[str] = mapped_column(String(255))
    model_architecture: Mapped[str] = mapped_column(String(100))
    model_version: Mapped[Optional[str]] = mapped_column(String(100))
    labels_json: Mapped[dict] = mapped_column(JSONB)
    model_card_sha256: Mapped[str] = mapped_column(String(64))
    classifier_sha256: Mapped[str] = mapped_column(String(64))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )

    predictions: Mapped[List["Prediction"]] = relationship(
        "Prediction", back_populates="model_metadata"
    )


class Prediction(Base):
    """Model output and reviewer relabel state for a classified document."""

    __tablename__ = "predictions"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    document_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("documents.id")
    )
    model_metadata_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("model_metadata.id")
    )
    predicted_class: Mapped[str] = mapped_column(String(100))
    top1_confidence: Mapped[float] = mapped_column(Float)
    class_scores_json: Mapped[dict] = mapped_column(JSONB)
    # Derived from top1_confidence < 0.7; set by inference worker at write time
    review_eligible: Mapped[bool] = mapped_column(Boolean, default=False)
    review_label: Mapped[Optional[str]] = mapped_column(String(100))
    reviewed_by_user_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id")
    )
    reviewed_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    document: Mapped["Document"] = relationship(
        "Document", back_populates="predictions"
    )
    model_metadata: Mapped["ModelMetadata"] = relationship(
        "ModelMetadata", back_populates="predictions"
    )
    reviewed_by: Mapped[Optional["User"]] = relationship("User")
    overlay_assets: Mapped[List["OverlayAsset"]] = relationship(
        "OverlayAsset", back_populates="prediction"
    )

    __table_args__ = (
        Index("ix_predictions_document_id", "document_id"),
        Index(
            "ix_predictions_review_queue",
            "review_eligible",
            postgresql_where="review_eligible IS TRUE",
        ),
    )


class OverlayAsset(Base):
    """Annotated PNG object location linked to a prediction."""

    __tablename__ = "overlay_assets"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    prediction_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("predictions.id")
    )
    blob_bucket: Mapped[str] = mapped_column(String(255))
    blob_key: Mapped[str] = mapped_column(String(1024))
    content_type: Mapped[str] = mapped_column(String(100), default="image/png")
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )

    prediction: Mapped["Prediction"] = relationship(
        "Prediction", back_populates="overlay_assets"
    )

    __table_args__ = (Index("ix_overlay_assets_prediction_id", "prediction_id"),)


class AuditEvent(Base):
    """Immutable append-only operational and security event log."""

    __tablename__ = "audit_events"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    # Nullable to support system/unauthenticated events; no FK to allow actor deletion
    actor_user_id: Mapped[Optional[uuid.UUID]] = mapped_column(UUID(as_uuid=True))
    action: Mapped[str] = mapped_column(String(100))
    target_type: Mapped[Optional[str]] = mapped_column(String(100))
    target_id: Mapped[Optional[str]] = mapped_column(String(255))
    outcome: Mapped[str] = mapped_column(String(50))
    details_json: Mapped[Optional[dict]] = mapped_column(JSONB)
    request_id: Mapped[Optional[str]] = mapped_column(String(255))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )

    __table_args__ = (
        Index("ix_audit_events_actor_user_id", "actor_user_id"),
        Index("ix_audit_events_action", "action"),
        Index("ix_audit_events_created_at", "created_at"),
        Index("ix_audit_events_target", "target_type", "target_id"),
    )
