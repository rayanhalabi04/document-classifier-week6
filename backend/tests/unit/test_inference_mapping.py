"""Unit tests for app/classifier/inference.py (T004)."""

import pytest
import torch
import torch.nn as nn

from app.classifier.inference import InferenceResult, run_inference
from app.classifier.validation import load_and_validate_model_card
from app.domain.model_metadata import RVL_CDIP_LABELS


class FixedLogitsModel(nn.Module):
    """Stub model that always returns the same logits."""

    def __init__(self, logits: list[float]):
        super().__init__()
        self._logits = torch.tensor([logits], dtype=torch.float32)

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        return self._logits


class TestRunInference:
    def test_returns_inference_result(self, model_card_file):
        card = load_and_validate_model_card(model_card_file)
        logits = [float(i) for i in range(16)]  # class 15 has highest logit
        model = FixedLogitsModel(logits)
        tensor = torch.zeros(1, 3, 224, 224)

        result = run_inference(model, tensor, card)
        assert isinstance(result, InferenceResult)

    def test_top1_class_matches_argmax(self, model_card_file):
        card = load_and_validate_model_card(model_card_file)
        # Class 11 (invoice) has the highest logit.
        logits = [0.0] * 16
        logits[11] = 10.0
        model = FixedLogitsModel(logits)
        tensor = torch.zeros(1, 3, 224, 224)

        result = run_inference(model, tensor, card)
        assert result.predicted_label_index == 11
        assert result.predicted_class == "invoice"

    def test_class_scores_contain_all_16_labels(self, model_card_file):
        card = load_and_validate_model_card(model_card_file)
        model = FixedLogitsModel([1.0] * 16)
        tensor = torch.zeros(1, 3, 224, 224)

        result = run_inference(model, tensor, card)
        assert set(result.class_scores.keys()) == set(RVL_CDIP_LABELS)

    def test_class_scores_sum_to_one(self, model_card_file):
        card = load_and_validate_model_card(model_card_file)
        model = FixedLogitsModel([float(i) for i in range(16)])
        tensor = torch.zeros(1, 3, 224, 224)

        result = run_inference(model, tensor, card)
        total = sum(result.class_scores.values())
        assert total == pytest.approx(1.0, abs=1e-5)

    def test_top1_confidence_matches_class_score(self, model_card_file):
        card = load_and_validate_model_card(model_card_file)
        logits = [0.0] * 16
        logits[5] = 8.0  # scientific report
        model = FixedLogitsModel(logits)
        tensor = torch.zeros(1, 3, 224, 224)

        result = run_inference(model, tensor, card)
        assert result.top1_confidence == pytest.approx(
            result.class_scores[result.predicted_class], abs=1e-6
        )

    def test_deterministic_output(self, model_card_file):
        """Same input always produces the same result."""
        card = load_and_validate_model_card(model_card_file)
        model = FixedLogitsModel([float(i) for i in range(16)])
        tensor = torch.zeros(1, 3, 224, 224)

        r1 = run_inference(model, tensor, card)
        r2 = run_inference(model, tensor, card)
        assert r1.predicted_label_index == r2.predicted_label_index
        assert r1.top1_confidence == pytest.approx(r2.top1_confidence)
