"""Loads a ConvNeXt Tiny/Small classifier from a state_dict checkpoint."""

from pathlib import Path

import torch
import torch.nn as nn
from torchvision.models import convnext_small, convnext_tiny

from app.classifier.validation import ClassifierValidationError
from app.domain.model_metadata import ModelCard


def build_model(backbone: str, num_classes: int = 16) -> nn.Module:
    """Build a ConvNeXt model with a num_classes-way head.

    The architecture is instantiated with random weights — we always overwrite
    them via `load_state_dict()` immediately after, so downloading ImageNet
    pretrained weights every cold start is wasteful and also fails inside the
    container (no writable HOME for torch hub cache).
    """
    if backbone == "convnext_tiny":
        model = convnext_tiny(weights=None)
    elif backbone == "convnext_small":
        model = convnext_small(weights=None)
    else:
        raise ClassifierValidationError(
            f"Unsupported backbone '{backbone}'. Use convnext_tiny or convnext_small."
        )

    # Replace the final Linear layer to match num_classes.
    # ConvNeXt classifier is Sequential(LayerNorm, Flatten, Linear).
    in_features = model.classifier[2].in_features
    model.classifier[2] = nn.Linear(in_features, num_classes)

    return model


def load_classifier(classifier_path: Path, model_card: ModelCard) -> nn.Module:
    """Load classifier.pt weights into the correct architecture.

    Returns the model in eval mode on CPU. The inference worker runs on
    CPU; the caller is responsible for moving to GPU if needed.

    Args:
        classifier_path: Path to classifier.pt (state_dict only).
        model_card: Validated ModelCard; provides backbone and num_classes.

    Raises:
        ClassifierValidationError: If the state_dict cannot be loaded.
    """
    model = build_model(model_card.backbone, model_card.num_classes)

    try:
        state_dict = torch.load(classifier_path, map_location="cpu")
        model.load_state_dict(state_dict)
    except Exception as exc:
        raise ClassifierValidationError(
            f"Failed to load state_dict from {classifier_path}: {exc}"
        ) from exc

    model.eval()
    return model


def dry_run_validation(model: nn.Module, image_size: int = 224) -> None:
    """Run a zero-tensor forward pass to confirm output dimension is 16.

    Raises ClassifierValidationError if output shape is wrong.
    """
    dummy = torch.zeros(1, 3, image_size, image_size)
    with torch.no_grad():
        out = model(dummy)

    if out.shape != (1, 16):
        raise ClassifierValidationError(
            f"Model output shape should be (1, 16), got {tuple(out.shape)}"
        )
