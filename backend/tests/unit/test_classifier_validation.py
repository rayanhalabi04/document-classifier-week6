"""Unit tests for app/classifier/validation.py (T001)."""

import json
from pathlib import Path

import pytest

from app.classifier.validation import (
    ClassifierValidationError,
    load_and_validate_model_card,
    validate_accuracy_threshold,
    validate_all,
    validate_classifier_checksum,
)
from app.domain.model_metadata import RVL_CDIP_LABELS


# ---------------------------------------------------------------------------
# load_and_validate_model_card
# ---------------------------------------------------------------------------


class TestLoadAndValidateModelCard:
    def test_valid_card_parses_correctly(self, model_card_file, valid_model_card_dict):
        card = load_and_validate_model_card(model_card_file)

        assert card.backbone == "convnext_tiny"
        assert card.num_classes == 16
        assert card.classes == RVL_CDIP_LABELS
        assert card.refuse_to_start_threshold == 0.6
        assert card.metrics.full_test_top1 == pytest.approx(0.6151)

    def test_missing_file_raises(self, tmp_path):
        with pytest.raises(ClassifierValidationError, match="not found"):
            load_and_validate_model_card(tmp_path / "missing.json")

    def test_invalid_json_raises(self, tmp_path):
        bad = tmp_path / "model_card.json"
        bad.write_text("{ not valid json }")
        with pytest.raises(ClassifierValidationError, match="not valid JSON"):
            load_and_validate_model_card(bad)

    def test_missing_required_key_raises(self, tmp_path, valid_model_card_dict):
        del valid_model_card_dict["backbone"]
        path = tmp_path / "model_card.json"
        path.write_text(json.dumps(valid_model_card_dict))
        with pytest.raises(ClassifierValidationError, match="missing required keys"):
            load_and_validate_model_card(path)

    def test_unsupported_architecture_raises(self, tmp_path, valid_model_card_dict):
        valid_model_card_dict["backbone"] = "resnet50"
        path = tmp_path / "model_card.json"
        path.write_text(json.dumps(valid_model_card_dict))
        with pytest.raises(ClassifierValidationError, match="Unsupported architecture"):
            load_and_validate_model_card(path)

    def test_convnext_small_is_accepted(self, tmp_path, valid_model_card_dict):
        valid_model_card_dict["backbone"] = "convnext_small"
        path = tmp_path / "model_card.json"
        path.write_text(json.dumps(valid_model_card_dict))
        card = load_and_validate_model_card(path)
        assert card.backbone == "convnext_small"

    def test_wrong_num_classes_raises(self, tmp_path, valid_model_card_dict):
        valid_model_card_dict["num_classes"] = 10
        path = tmp_path / "model_card.json"
        path.write_text(json.dumps(valid_model_card_dict))
        with pytest.raises(ClassifierValidationError, match="num_classes must be 16"):
            load_and_validate_model_card(path)

    def test_wrong_class_list_length_raises(self, tmp_path, valid_model_card_dict):
        valid_model_card_dict["classes"] = ["letter", "form"]
        path = tmp_path / "model_card.json"
        path.write_text(json.dumps(valid_model_card_dict))
        with pytest.raises(ClassifierValidationError):
            load_and_validate_model_card(path)

    def test_wrong_class_order_raises(self, tmp_path, valid_model_card_dict):
        shuffled = list(reversed(RVL_CDIP_LABELS))
        valid_model_card_dict["classes"] = shuffled
        path = tmp_path / "model_card.json"
        path.write_text(json.dumps(valid_model_card_dict))
        with pytest.raises(ClassifierValidationError, match="RVL-CDIP labels"):
            load_and_validate_model_card(path)

    def test_missing_artifact_key_raises(self, tmp_path, valid_model_card_dict):
        del valid_model_card_dict["artifact"]["sha256"]
        path = tmp_path / "model_card.json"
        path.write_text(json.dumps(valid_model_card_dict))
        with pytest.raises(ClassifierValidationError, match="artifact missing key"):
            load_and_validate_model_card(path)


# ---------------------------------------------------------------------------
# validate_classifier_checksum
# ---------------------------------------------------------------------------


class TestValidateClassifierChecksum:
    def test_correct_sha_passes(self, fake_classifier_file):
        classifier_path, card_path = fake_classifier_file
        card = load_and_validate_model_card(card_path)
        validate_classifier_checksum(classifier_path, card)  # should not raise

    def test_missing_file_raises(self, model_card_file, tmp_path):
        card = load_and_validate_model_card(model_card_file)
        with pytest.raises(ClassifierValidationError, match="not found"):
            validate_classifier_checksum(tmp_path / "missing.pt", card)

    def test_sha_mismatch_raises(self, fake_classifier_file, tmp_path):
        _, card_path = fake_classifier_file
        card = load_and_validate_model_card(card_path)

        # Write a different file — SHA will differ.
        wrong_file = tmp_path / "wrong.pt"
        wrong_file.write_bytes(b"different-content")

        with pytest.raises(ClassifierValidationError, match="checksum mismatch"):
            validate_classifier_checksum(wrong_file, card)


# ---------------------------------------------------------------------------
# validate_accuracy_threshold
# ---------------------------------------------------------------------------


class TestValidateAccuracyThreshold:
    def test_above_threshold_passes(self, model_card_file):
        card = load_and_validate_model_card(model_card_file)
        # card has top1=0.6151, threshold=0.6 → should pass
        validate_accuracy_threshold(card)

    def test_below_threshold_raises(self, tmp_path, valid_model_card_dict):
        valid_model_card_dict["refuse_to_start_threshold"] = 0.9
        path = tmp_path / "model_card.json"
        path.write_text(json.dumps(valid_model_card_dict))
        card = load_and_validate_model_card(path)

        with pytest.raises(ClassifierValidationError, match="below"):
            validate_accuracy_threshold(card)


# ---------------------------------------------------------------------------
# validate_all (integration of the three checks)
# ---------------------------------------------------------------------------


class TestValidateAll:
    def test_valid_assets_return_model_card(self, fake_classifier_file):
        classifier_path, card_path = fake_classifier_file
        card = validate_all(classifier_path, card_path)
        assert card.num_classes == 16

    def test_bad_sha_raises(self, fake_classifier_file, tmp_path):
        _, card_path = fake_classifier_file
        wrong_pt = tmp_path / "wrong.pt"
        wrong_pt.write_bytes(b"not the right file")
        with pytest.raises(ClassifierValidationError):
            validate_all(wrong_pt, card_path)
