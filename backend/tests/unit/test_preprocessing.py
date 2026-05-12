"""Unit tests for app/classifier/preprocessing.py (T003)."""

import pytest
import torch
from PIL import Image

from app.classifier.preprocessing import PreprocessingError, load_tiff, preprocess
from app.classifier.validation import load_and_validate_model_card


class TestLoadTiff:
    def test_loads_valid_grayscale_tiff(self, grayscale_tiff):
        img = load_tiff(grayscale_tiff)
        assert img is not None

    def test_missing_file_raises(self, tmp_path):
        with pytest.raises(PreprocessingError, match="not found"):
            load_tiff(tmp_path / "missing.tif")

    def test_corrupt_file_raises(self, tmp_path):
        bad = tmp_path / "corrupt.tif"
        bad.write_bytes(b"this is not an image")
        with pytest.raises(PreprocessingError, match="Cannot read"):
            load_tiff(bad)


class TestPreprocess:
    def test_output_shape_is_correct(self, grayscale_tiff, model_card_file):
        card = load_and_validate_model_card(model_card_file)
        tensor = preprocess(grayscale_tiff, card)
        assert tensor.shape == (1, 3, 224, 224)

    def test_output_is_float32(self, grayscale_tiff, model_card_file):
        card = load_and_validate_model_card(model_card_file)
        tensor = preprocess(grayscale_tiff, card)
        assert tensor.dtype == torch.float32

    def test_rgb_image_also_works(self, tmp_path, model_card_file):
        """Non-grayscale inputs should also be handled via convert('RGB')."""
        path = tmp_path / "rgb.tif"
        Image.new("RGB", (64, 64), color=(100, 150, 200)).save(path, format="TIFF")
        card = load_and_validate_model_card(model_card_file)
        tensor = preprocess(path, card)
        assert tensor.shape == (1, 3, 224, 224)

    def test_missing_file_raises(self, tmp_path, model_card_file):
        card = load_and_validate_model_card(model_card_file)
        with pytest.raises(PreprocessingError):
            preprocess(tmp_path / "missing.tif", card)
