"""Shared fixtures for unit tests."""

import hashlib
import json
from pathlib import Path

import pytest
from PIL import Image

from app.domain.model_metadata import RVL_CDIP_LABELS


@pytest.fixture()
def valid_model_card_dict() -> dict:
    return {
        "name": "rvl_cdip_convnext_tiny",
        "version": "v0.1.0-week6",
        "backbone": "convnext_tiny",
        "num_classes": 16,
        "classes": RVL_CDIP_LABELS,
        "input": {
            "image_size": 224,
            "channels": 3,
            "normalization": {
                "mean": [0.485, 0.456, 0.406],
                "std": [0.229, 0.224, 0.225],
            },
        },
        "artifact": {
            "sha256": "deadbeef" * 8,
            "size_bytes": 111396999,
            "path": "app/classifier/models/classifier.pt",
        },
        "metrics": {
            "full_test": {"top1": 0.6151, "top5": 0.8992, "n": 40000}
        },
        "refuse_to_start_threshold": 0.6,
    }


@pytest.fixture()
def model_card_file(tmp_path, valid_model_card_dict) -> Path:
    """Write a valid model_card.json to a temp file."""
    path = tmp_path / "model_card.json"
    path.write_text(json.dumps(valid_model_card_dict))
    return path


@pytest.fixture()
def fake_classifier_file(tmp_path, valid_model_card_dict) -> tuple[Path, dict]:
    """Write a small fake binary file and patch its SHA into the card dict."""
    classifier_path = tmp_path / "classifier.pt"
    classifier_path.write_bytes(b"fake-weights-data")

    sha = hashlib.sha256(b"fake-weights-data").hexdigest()
    valid_model_card_dict["artifact"]["sha256"] = sha

    card_path = tmp_path / "model_card.json"
    card_path.write_text(json.dumps(valid_model_card_dict))

    return classifier_path, card_path


@pytest.fixture()
def grayscale_tiff(tmp_path) -> Path:
    """Create a small 64x64 grayscale TIFF."""
    path = tmp_path / "test_doc.tif"
    Image.new("L", (64, 64), color=128).save(path, format="TIFF")
    return path
