"""Runs model inference and maps logits to RVL-CDIP labels."""

from dataclasses import dataclass

import torch
import torch.nn as nn

from app.domain.model_metadata import ModelCard


@dataclass(frozen=True)
class InferenceResult:
    """Output of a single inference pass."""

    predicted_class: str          # top-1 RVL-CDIP label
    predicted_label_index: int    # 0–15
    top1_confidence: float        # softmax probability of top-1 class
    class_scores: dict[str, float]  # full softmax distribution, keyed by label


def run_inference(
    model: nn.Module,
    tensor: torch.Tensor,
    model_card: ModelCard,
) -> InferenceResult:
    """Run a forward pass and return a structured InferenceResult.

    Inference runs on CPU in float32 with no AMP, matching the Docker
    production environment and golden-set replay contract.

    Args:
        model: Model in eval mode (output of loader.load_classifier).
        tensor: Preprocessed (1, 3, H, W) float32 tensor on CPU.
        model_card: Validated ModelCard; provides the class name list.

    Returns:
        InferenceResult with top-1 class, confidence, and full class scores.
    """
    model.eval()

    with torch.no_grad():
        logits = model(tensor.float())  # float32, no AMP

    probs = torch.softmax(logits, dim=1)[0]  # shape (16,)

    top1_idx = int(probs.argmax().item())
    top1_conf = float(probs[top1_idx].item())

    class_scores = {
        label: float(probs[i].item())
        for i, label in enumerate(model_card.classes)
    }

    return InferenceResult(
        predicted_class=model_card.classes[top1_idx],
        predicted_label_index=top1_idx,
        top1_confidence=top1_conf,
        class_scores=class_scores,
    )
