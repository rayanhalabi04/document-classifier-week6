"""Inference worker — consumes RQ classification jobs.

Startup runs all dependency checks (classifier assets, MinIO, RQ, Redis) and
refuses to start if any check fails. Once startup passes, the worker blocks
on the 'classification' RQ queue and processes one job at a time.

Each job:
  1. Marks the classification_job row as running.
  2. Downloads the original TIFF from MinIO.
  3. Runs preprocessing + inference + overlay generation.
  4. Uploads the overlay PNG to MinIO.
  5. Persists the prediction + overlay asset in one DB transaction.
  6. On error, marks the job retryable_failed and re-raises so RQ retries.
"""

import logging
import sys
import tempfile
import uuid
from pathlib import Path
from typing import Optional, Tuple

import torch.nn as nn

from app.classifier.inference import InferenceResult, run_inference
from app.classifier.loader import load_classifier
from app.classifier.overlays import generate_overlay
from app.classifier.preprocessing import preprocess
from app.classifier.validation import validate_all
from app.db.session import SessionFactory
from app.domain.errors import ClassificationError
from app.domain.model_metadata import ModelCard
from app.infra.minio import ORIGINALS_BUCKET, OVERLAYS_BUCKET, MinIOAdapter
from app.repositories.documents import DocumentRepository
from app.repositories.jobs import ClassificationJobRepository
from app.services.classification_jobs import ClassificationJobService
from app.services.startup_validation import run_inference_worker_checks

logger = logging.getLogger(__name__)

_MODELS_DIR = Path(__file__).parent.parent / "classifier" / "models"
_CLASSIFIER_PATH = _MODELS_DIR / "classifier.pt"
_MODEL_CARD_PATH = _MODELS_DIR / "model_card.json"

_model_cache: Optional[Tuple[nn.Module, ModelCard]] = None


def _get_model() -> Tuple[nn.Module, ModelCard]:
    """Load the model once per worker process and cache it."""
    global _model_cache
    if _model_cache is None:
        model_card = validate_all(_CLASSIFIER_PATH, _MODEL_CARD_PATH)
        model = load_classifier(_CLASSIFIER_PATH, model_card)
        _model_cache = (model, model_card)
    return _model_cache


def classify_document(document_id: str, model_metadata_id: str) -> None:
    """RQ job — run inference on one document and persist the result.

    Args:
        document_id: UUID string of the document to classify.
        model_metadata_id: UUID string of the model version producing the result.
    """
    doc_uuid = uuid.UUID(document_id)
    meta_uuid = uuid.UUID(model_metadata_id)

    with SessionFactory() as session:
        job_repo = ClassificationJobRepository(session)
        doc_repo = DocumentRepository(session)
        svc = ClassificationJobService(session)

        job = job_repo.get_active_by_document(doc_uuid)
        if job is None:
            raise ClassificationError(
                f"No active classification job for document {document_id}"
            )

        svc.mark_running(job.id)

        try:
            doc = doc_repo.get_by_id(doc_uuid)
            if doc is None:
                raise ClassificationError(f"Document {document_id} not found")
            if doc.blob_key is None:
                raise ClassificationError(
                    f"Document {document_id} has no stored blob"
                )

            result, overlay_png = _run_pipeline(doc.blob_key)

            overlay_key = f"overlays/{document_id}.png"
            minio = MinIOAdapter()
            minio.upload_file(
                bucket=OVERLAYS_BUCKET,
                key=overlay_key,
                data=overlay_png,
                content_type="image/png",
            )

            svc.persist_result(
                job_id=job.id,
                document_id=doc_uuid,
                model_metadata_id=meta_uuid,
                predicted_class=result.predicted_class,
                top1_confidence=result.top1_confidence,
                class_scores=result.class_scores,
                blob_bucket=OVERLAYS_BUCKET,
                blob_key=overlay_key,
                batch_id=doc.batch_id,
            )

            logger.info(
                "Classified document %s as '%s' (%.2f%%)",
                document_id,
                result.predicted_class,
                result.top1_confidence * 100,
            )

        except Exception as exc:
            logger.exception(
                "Classification failed for document %s (job %s)", document_id, job.id
            )
            svc.mark_retryable_failure(job.id, str(exc))
            raise


def _run_pipeline(blob_key: str) -> Tuple[InferenceResult, bytes]:
    """Download TIFF, run inference, generate overlay PNG.

    Returns the inference result and the encoded overlay PNG bytes.
    """
    model, model_card = _get_model()
    minio = MinIOAdapter()
    tiff_bytes = minio.download_file(ORIGINALS_BUCKET, blob_key)

    with tempfile.NamedTemporaryFile(suffix=".tiff", delete=False) as tmp:
        tmp.write(tiff_bytes)
        tmp_path = Path(tmp.name)

    try:
        tensor = preprocess(tmp_path, model_card)
        result = run_inference(model, tensor, model_card)
        overlay = generate_overlay(tmp_path, result)
    finally:
        tmp_path.unlink(missing_ok=True)

    return result, overlay.png_bytes


def main() -> None:
    """Inference worker entrypoint — validate startup then consume jobs."""
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    )

    logger.info("Starting inference worker startup checks...")
    failures = run_inference_worker_checks()
    if failures:
        for msg in failures:
            logger.error("Startup check failed: %s", msg)
        sys.exit(1)

    from app.config import apply_vault_secrets

    apply_vault_secrets()

    logger.info("All startup checks passed. Connecting to RQ...")

    from rq import Queue, Worker

    from app.infra.redis import get_redis_client

    redis_client = get_redis_client()
    queues = [Queue("classification", connection=redis_client)]
    worker = Worker(queues, connection=redis_client)

    logger.info("Inference worker ready. Listening on 'classification' queue.")
    worker.work()


if __name__ == "__main__":
    main()
