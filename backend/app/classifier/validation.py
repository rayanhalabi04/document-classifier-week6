"""Validates classifier assets before the inference worker consumes jobs."""

import hashlib
import json
from pathlib import Path

from app.domain.model_metadata import (
    ModelCard,
    ModelCardArtifact,
    ModelCardInput,
    ModelCardMetrics,
    RVL_CDIP_LABELS,
    SUPPORTED_ARCHITECTURES,
)


class ClassifierValidationError(Exception):
    """Raised when classifier assets fail validation."""


def _sha256(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        while chunk := f.read(1024 * 1024):
            h.update(chunk)
    return h.hexdigest()


def load_and_validate_model_card(model_card_path: Path) -> ModelCard:
    """Parse model_card.json and validate its structure.

    Raises ClassifierValidationError for any structural problem.
    """
    if not model_card_path.exists():
        raise ClassifierValidationError(
            f"model_card.json not found: {model_card_path}"
        )

    try:
        with open(model_card_path) as f:
            raw = json.load(f)
    except json.JSONDecodeError as exc:
        raise ClassifierValidationError(
            f"model_card.json is not valid JSON: {exc}"
        ) from exc

    # Required top-level keys.
    required = {
        "backbone", "num_classes", "classes", "artifact",
        "input", "metrics", "refuse_to_start_threshold",
    }
    missing = required - raw.keys()
    if missing:
        raise ClassifierValidationError(
            f"model_card.json missing required keys: {missing}"
        )

    # Architecture must be a supported ConvNeXt variant.
    backbone = raw["backbone"]
    if backbone not in SUPPORTED_ARCHITECTURES:
        raise ClassifierValidationError(
            f"Unsupported architecture '{backbone}'. "
            f"Supported: {SUPPORTED_ARCHITECTURES}"
        )

    # Must declare exactly 16 classes.
    if raw["num_classes"] != 16:
        raise ClassifierValidationError(
            f"num_classes must be 16, got {raw['num_classes']}"
        )

    classes = raw["classes"]
    if not isinstance(classes, list) or len(classes) != 16:
        raise ClassifierValidationError(
            f"'classes' must be a list of 16 labels, got {len(classes) if isinstance(classes, list) else type(classes)}"
        )

    # Class list must match the official RVL-CDIP ordering.
    if classes != RVL_CDIP_LABELS:
        mismatches = [
            f"index {i}: expected '{e}', got '{g}'"
            for i, (e, g) in enumerate(zip(RVL_CDIP_LABELS, classes))
            if e != g
        ]
        raise ClassifierValidationError(
            f"Class list does not match RVL-CDIP labels: {mismatches}"
        )

    # Artifact block.
    artifact_raw = raw.get("artifact", {})
    for key in ("sha256", "size_bytes", "path"):
        if key not in artifact_raw:
            raise ClassifierValidationError(
                f"model_card.json artifact missing key: '{key}'"
            )
    artifact = ModelCardArtifact(
        sha256=artifact_raw["sha256"],
        size_bytes=artifact_raw["size_bytes"],
        path=artifact_raw["path"],
    )

    # Input config.
    inp = raw.get("input", {})
    norm = inp.get("normalization", {})
    input_config = ModelCardInput(
        image_size=inp.get("image_size", 224),
        channels=inp.get("channels", 3),
        normalization_mean=norm.get("mean", [0.485, 0.456, 0.406]),
        normalization_std=norm.get("std", [0.229, 0.224, 0.225]),
    )

    # Metrics.
    full_test = raw.get("metrics", {}).get("full_test", {})
    metrics = ModelCardMetrics(
        full_test_top1=full_test.get("top1", 0.0),
        full_test_top5=full_test.get("top5", 0.0),
        full_test_n=full_test.get("n", 0),
    )

    return ModelCard(
        name=raw.get("name", ""),
        version=raw.get("version", ""),
        backbone=backbone,
        num_classes=raw["num_classes"],
        classes=classes,
        artifact=artifact,
        input_config=input_config,
        metrics=metrics,
        refuse_to_start_threshold=float(raw["refuse_to_start_threshold"]),
        raw=raw,
    )


def validate_classifier_checksum(
    classifier_path: Path, model_card: ModelCard
) -> None:
    """Verify classifier.pt SHA-256 matches model_card.json.

    Raises ClassifierValidationError on mismatch or missing file.
    """
    if not classifier_path.exists():
        raise ClassifierValidationError(
            f"classifier.pt not found: {classifier_path}"
        )

    actual = _sha256(classifier_path)
    expected = model_card.artifact.sha256

    if actual != expected:
        raise ClassifierValidationError(
            f"classifier.pt checksum mismatch.\n"
            f"  Expected: {expected}\n"
            f"  Actual:   {actual}"
        )


def validate_accuracy_threshold(model_card: ModelCard) -> None:
    """Refuse to start if recorded test accuracy is below threshold.

    Raises ClassifierValidationError when the model card's own metrics
    do not meet its declared refuse_to_start_threshold.
    """
    top1 = model_card.metrics.full_test_top1
    threshold = model_card.refuse_to_start_threshold

    if top1 < threshold:
        raise ClassifierValidationError(
            f"Model full-test top-1 ({top1:.4f}) is below "
            f"refuse_to_start_threshold ({threshold}). "
            "Retrain or lower the threshold in model_card.json."
        )


def validate_all(classifier_path: Path, model_card_path: Path) -> ModelCard:
    """Run all validation checks and return the parsed ModelCard.

    Convenience wrapper for inference worker startup.
    """
    model_card = load_and_validate_model_card(model_card_path)
    validate_classifier_checksum(classifier_path, model_card)
    validate_accuracy_threshold(model_card)
    return model_card


_DEFAULT_MODELS_DIR = Path(__file__).parent / "models"


def validate_classifier_assets() -> ModelCard:
    """Validate classifier assets at their default location.

    Used by the inference worker startup check. Reads classifier.pt and
    model_card.json from `app/classifier/models/`.
    """
    return validate_all(
        classifier_path=_DEFAULT_MODELS_DIR / "classifier.pt",
        model_card_path=_DEFAULT_MODELS_DIR / "model_card.json",
    )
