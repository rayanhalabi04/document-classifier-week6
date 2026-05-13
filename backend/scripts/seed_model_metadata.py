"""Seed a model_metadata row from the local model_card.json and classifier.pt.

Idempotent: skips insertion if a row with the same classifier_sha256 already
exists. Reads model card + classifier hash from
`backend/app/classifier/models/` (path baked into the Docker image).
"""

import hashlib
import json
import uuid
from datetime import datetime, timezone
from pathlib import Path

from app.db.models import ModelMetadata
from app.db.session import SessionFactory

_MODELS_DIR = (
    Path(__file__).parent.parent / "app" / "classifier" / "models"
)
_CLASSIFIER_PATH = _MODELS_DIR / "classifier.pt"
_MODEL_CARD_PATH = _MODELS_DIR / "model_card.json"


def _sha256(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        while chunk := f.read(1024 * 1024):
            h.update(chunk)
    return h.hexdigest()


def main() -> None:
    if not _CLASSIFIER_PATH.exists() or not _MODEL_CARD_PATH.exists():
        raise SystemExit("Classifier assets not found — cannot seed model_metadata.")

    with open(_MODEL_CARD_PATH) as f:
        card = json.load(f)

    classifier_sha = _sha256(_CLASSIFIER_PATH)
    model_card_sha = _sha256(_MODEL_CARD_PATH)

    with SessionFactory() as session:
        existing = (
            session.query(ModelMetadata)
            .filter(ModelMetadata.classifier_sha256 == classifier_sha)
            .first()
        )
        if existing:
            print(f"model_metadata row already exists (id={existing.id}). Skipping.")
            return

        row = ModelMetadata(
            id=uuid.uuid4(),
            model_name=card.get("name", "rvl-cdip-convnext"),
            model_architecture=card.get("backbone", "convnext_tiny"),
            model_version=card.get("version", "0.1.0"),
            labels_json={"classes": card.get("classes", [])},
            model_card_sha256=model_card_sha,
            classifier_sha256=classifier_sha,
            created_at=datetime.now(timezone.utc),
        )
        session.add(row)
        session.commit()
        print(f"Inserted model_metadata id={row.id}")


if __name__ == "__main__":
    main()
