"""initial schema

Revision ID: 001
Revises:
Create Date: 2026-05-11

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "001"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # --- ENUM types (must exist before tables that use them) ---
    batchstatus = sa.Enum(
        "pending", "processing", "completed", "failed",
        name="batchstatus",
    )
    ingestionstatus = sa.Enum(
        "pending", "stored", "queued", "processing", "completed", "failed",
        name="ingestionstatus",
    )
    jobstatus = sa.Enum(
        "queued", "running", "succeeded", "retryable_failed", "terminal_failed",
        name="jobstatus",
    )
    # Types auto-created via before_create event when tables reference them.

    # --- users ---
    op.create_table(
        "users",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("email", sa.String(length=320), nullable=False),
        sa.Column("hashed_password", sa.String(length=1024), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default="true"),
        sa.Column("is_verified", sa.Boolean(), nullable=False, server_default="false"),
        sa.Column("is_superuser", sa.Boolean(), nullable=False, server_default="false"),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.Column("last_login_at", sa.DateTime(timezone=True), nullable=True),
        sa.UniqueConstraint("email", name="uq_users_email"),
    )

    # --- casbin_rule ---
    op.create_table(
        "casbin_rule",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("ptype", sa.String(length=255), nullable=True),
        sa.Column("v0", sa.String(length=255), nullable=True),
        sa.Column("v1", sa.String(length=255), nullable=True),
        sa.Column("v2", sa.String(length=255), nullable=True),
        sa.Column("v3", sa.String(length=255), nullable=True),
        sa.Column("v4", sa.String(length=255), nullable=True),
        sa.Column("v5", sa.String(length=255), nullable=True),
    )

    # --- role_assignments ---
    op.create_table(
        "role_assignments",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "user_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("role", sa.String(length=50), nullable=False),
        sa.Column(
            "assigned_by_user_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("users.id"),
            nullable=True,
        ),
        sa.Column(
            "assigned_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.Column("revoked_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index(
        "ix_role_assignments_user_active",
        "role_assignments",
        ["user_id", "role"],
        postgresql_where=sa.text("revoked_at IS NULL"),
    )

    # --- batches ---
    op.create_table(
        "batches",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("source", sa.String(length=255), nullable=False),
        sa.Column(
            "status",
            batchstatus,
            nullable=False,
            server_default="pending",
        ),
        sa.Column("document_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("reviewable_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index("ix_batches_status", "batches", ["status"])
    op.create_index("ix_batches_created_at", "batches", ["created_at"])

    # --- documents ---
    op.create_table(
        "documents",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "batch_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("batches.id"),
            nullable=False,
        ),
        sa.Column("source_path", sa.String(length=1024), nullable=False),
        sa.Column("source_filename", sa.String(length=512), nullable=False),
        sa.Column("source_size_bytes", sa.Integer(), nullable=True),
        sa.Column("source_checksum", sa.String(length=64), nullable=True),
        sa.Column("blob_bucket", sa.String(length=255), nullable=True),
        sa.Column("blob_key", sa.String(length=1024), nullable=True),
        sa.Column("mime_type", sa.String(length=255), nullable=True),
        sa.Column(
            "ingestion_status",
            ingestionstatus,
            nullable=False,
            server_default="pending",
        ),
        sa.Column("failure_reason", sa.Text(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
    )
    op.create_index("ix_documents_batch_id", "documents", ["batch_id"])
    op.create_index("ix_documents_source_checksum", "documents", ["source_checksum"])
    op.create_index(
        "ix_documents_source_identity_active",
        "documents",
        ["source_checksum", "source_path"],
        postgresql_where=sa.text("ingestion_status NOT IN ('failed')"),
    )

    # --- classification_jobs ---
    op.create_table(
        "classification_jobs",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "document_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("documents.id"),
            nullable=False,
        ),
        sa.Column("rq_job_id", sa.String(length=255), nullable=True),
        sa.Column(
            "status",
            jobstatus,
            nullable=False,
            server_default="queued",
        ),
        sa.Column("attempt_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("last_error", sa.Text(), nullable=True),
        sa.Column("enqueued_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("finished_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index(
        "ix_classification_jobs_document_id", "classification_jobs", ["document_id"]
    )
    op.create_index(
        "ix_classification_jobs_status", "classification_jobs", ["status"]
    )

    # --- model_metadata ---
    op.create_table(
        "model_metadata",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("model_name", sa.String(length=255), nullable=False),
        sa.Column("model_architecture", sa.String(length=100), nullable=False),
        sa.Column("model_version", sa.String(length=100), nullable=True),
        sa.Column("labels_json", postgresql.JSONB(), nullable=False),
        sa.Column("model_card_sha256", sa.String(length=64), nullable=False),
        sa.Column("classifier_sha256", sa.String(length=64), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
    )

    # --- predictions ---
    op.create_table(
        "predictions",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "document_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("documents.id"),
            nullable=False,
        ),
        sa.Column(
            "model_metadata_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("model_metadata.id"),
            nullable=False,
        ),
        sa.Column("predicted_class", sa.String(length=100), nullable=False),
        sa.Column("top1_confidence", sa.Float(), nullable=False),
        sa.Column("class_scores_json", postgresql.JSONB(), nullable=False),
        sa.Column("review_eligible", sa.Boolean(), nullable=False, server_default="false"),
        sa.Column("review_label", sa.String(length=100), nullable=True),
        sa.Column(
            "reviewed_by_user_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("users.id"),
            nullable=True,
        ),
        sa.Column("reviewed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
    )
    op.create_index("ix_predictions_document_id", "predictions", ["document_id"])
    op.create_index(
        "ix_predictions_review_queue",
        "predictions",
        ["review_eligible"],
        postgresql_where=sa.text("review_eligible IS TRUE"),
    )

    # --- overlay_assets ---
    op.create_table(
        "overlay_assets",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "prediction_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("predictions.id"),
            nullable=False,
        ),
        sa.Column("blob_bucket", sa.String(length=255), nullable=False),
        sa.Column("blob_key", sa.String(length=1024), nullable=False),
        sa.Column("content_type", sa.String(length=100), nullable=False, server_default="image/png"),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
    )
    op.create_index(
        "ix_overlay_assets_prediction_id", "overlay_assets", ["prediction_id"]
    )

    # --- audit_events ---
    op.create_table(
        "audit_events",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("actor_user_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("action", sa.String(length=100), nullable=False),
        sa.Column("target_type", sa.String(length=100), nullable=True),
        sa.Column("target_id", sa.String(length=255), nullable=True),
        sa.Column("outcome", sa.String(length=50), nullable=False),
        sa.Column("details_json", postgresql.JSONB(), nullable=True),
        sa.Column("request_id", sa.String(length=255), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
    )
    op.create_index("ix_audit_events_actor_user_id", "audit_events", ["actor_user_id"])
    op.create_index("ix_audit_events_action", "audit_events", ["action"])
    op.create_index("ix_audit_events_created_at", "audit_events", ["created_at"])
    op.create_index(
        "ix_audit_events_target", "audit_events", ["target_type", "target_id"]
    )


def downgrade() -> None:
    # Drop tables in reverse dependency order
    op.drop_table("audit_events")
    op.drop_table("overlay_assets")
    op.drop_table("predictions")
    op.drop_table("model_metadata")
    op.drop_table("classification_jobs")
    op.drop_table("documents")
    op.drop_table("batches")
    op.drop_table("role_assignments")
    op.drop_table("casbin_rule")
    op.drop_table("users")

    # Drop ENUM types after tables are gone
    sa.Enum(name="jobstatus").drop(op.get_bind())
    sa.Enum(name="ingestionstatus").drop(op.get_bind())
    sa.Enum(name="batchstatus").drop(op.get_bind())
