"""Unit tests for app/classifier/overlays.py (T005)."""

import io

import pytest
from PIL import Image

from app.classifier.inference import InferenceResult
from app.classifier.overlays import OverlayError, OverlayResult, generate_overlay
from app.domain.model_metadata import RVL_CDIP_LABELS


def _make_result(label_index: int = 11, confidence: float = 0.92) -> InferenceResult:
    scores = {label: 0.0 for label in RVL_CDIP_LABELS}
    scores[RVL_CDIP_LABELS[label_index]] = confidence
    return InferenceResult(
        predicted_class=RVL_CDIP_LABELS[label_index],
        predicted_label_index=label_index,
        top1_confidence=confidence,
        class_scores=scores,
    )


class TestGenerateOverlay:
    def test_returns_overlay_result(self, grayscale_tiff):
        result = generate_overlay(grayscale_tiff, _make_result())
        assert isinstance(result, OverlayResult)

    def test_png_bytes_are_valid(self, grayscale_tiff):
        result = generate_overlay(grayscale_tiff, _make_result())
        img = Image.open(io.BytesIO(result.png_bytes))
        assert img.format == "PNG"

    def test_overlay_taller_than_source(self, grayscale_tiff):
        """Canvas should be taller than the source due to the banner."""
        source = Image.open(grayscale_tiff)
        _, source_h = source.size
        result = generate_overlay(grayscale_tiff, _make_result())
        assert result.height > source_h

    def test_width_unchanged(self, grayscale_tiff):
        source = Image.open(grayscale_tiff)
        source_w, _ = source.size
        result = generate_overlay(grayscale_tiff, _make_result())
        assert result.width == source_w

    def test_missing_source_raises(self, tmp_path):
        with pytest.raises(OverlayError, match="Cannot open"):
            generate_overlay(tmp_path / "missing.tif", _make_result())

    def test_high_confidence_produces_png(self, grayscale_tiff):
        result = generate_overlay(grayscale_tiff, _make_result(confidence=0.95))
        assert len(result.png_bytes) > 0

    def test_low_confidence_produces_png(self, grayscale_tiff):
        result = generate_overlay(grayscale_tiff, _make_result(confidence=0.45))
        assert len(result.png_bytes) > 0
