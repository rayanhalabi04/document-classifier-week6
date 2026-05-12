"""Unit tests for app/classifier/loader.py (T002)."""

import torch
import torch.nn as nn
import pytest

from app.classifier.loader import build_model, dry_run_validation
from app.classifier.validation import ClassifierValidationError


class TestBuildModel:
    def test_convnext_tiny_output_shape(self):
        model = build_model("convnext_tiny", num_classes=16)
        dummy = torch.zeros(1, 3, 224, 224)
        with torch.no_grad():
            out = model(dummy)
        assert out.shape == (1, 16)

    def test_convnext_small_output_shape(self):
        model = build_model("convnext_small", num_classes=16)
        dummy = torch.zeros(1, 3, 224, 224)
        with torch.no_grad():
            out = model(dummy)
        assert out.shape == (1, 16)

    def test_unsupported_backbone_raises(self):
        with pytest.raises(ClassifierValidationError, match="Unsupported backbone"):
            build_model("resnet50")

    def test_model_is_in_eval_mode_after_load(self, fake_classifier_file):
        from app.classifier.loader import load_classifier
        from app.classifier.validation import load_and_validate_model_card

        classifier_path, card_path = fake_classifier_file
        card = load_and_validate_model_card(card_path)

        # Save a real tiny state_dict so load_classifier can load it.
        model = build_model(card.backbone, card.num_classes)
        torch.save(model.state_dict(), classifier_path)

        loaded = load_classifier(classifier_path, card)
        assert not loaded.training  # eval mode

    def test_head_has_correct_output_features(self):
        model = build_model("convnext_tiny", num_classes=16)
        head_linear = model.classifier[2]
        assert isinstance(head_linear, nn.Linear)
        assert head_linear.out_features == 16


class TestDryRunValidation:
    def test_passes_for_valid_model(self):
        model = build_model("convnext_tiny")
        model.eval()
        dry_run_validation(model, image_size=224)  # should not raise

    def test_fails_for_wrong_output_dimension(self):
        # Build a model with wrong num_classes to force shape mismatch.
        model = build_model("convnext_tiny", num_classes=10)
        model.eval()
        with pytest.raises(ClassifierValidationError, match="output shape"):
            dry_run_validation(model, image_size=224)
