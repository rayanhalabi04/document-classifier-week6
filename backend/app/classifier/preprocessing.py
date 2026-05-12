"""Preprocesses grayscale TIFF images into model-ready tensors."""

from pathlib import Path

import torch
from PIL import Image, UnidentifiedImageError
from torchvision import transforms as T

from app.domain.model_metadata import ModelCard

# ImageNet normalisation constants used during training.
_IMAGENET_MEAN = [0.485, 0.456, 0.406]
_IMAGENET_STD = [0.229, 0.224, 0.225]


class PreprocessingError(Exception):
    """Raised when an image cannot be preprocessed."""


def build_eval_transform(model_card: ModelCard) -> T.Compose:
    """Build the eval-time transform pipeline from model card settings.

    Matches the notebook's eval_tfm exactly:
      Resize(256) → CenterCrop(image_size) → convert to RGB → ToTensor → Normalize
    """
    size = model_card.input_config.image_size
    mean = model_card.input_config.normalization_mean
    std = model_card.input_config.normalization_std

    return T.Compose([
        T.Resize(256),
        T.CenterCrop(size),
        T.Lambda(lambda img: img.convert("RGB")),
        T.ToTensor(),
        T.Normalize(mean=mean, std=std),
    ])


def load_tiff(image_path: Path) -> Image.Image:
    """Open a TIFF file and verify it is readable.

    Raises PreprocessingError for unreadable or unsupported files.
    """
    if not image_path.exists():
        raise PreprocessingError(f"Image file not found: {image_path}")

    try:
        img = Image.open(image_path)
        img.load()  # force full decode to catch corrupt files early
    except (UnidentifiedImageError, OSError) as exc:
        raise PreprocessingError(
            f"Cannot read image {image_path}: {exc}"
        ) from exc

    return img


def preprocess(image_path: Path, model_card: ModelCard) -> torch.Tensor:
    """Load a grayscale TIFF and return a (1, 3, H, W) float32 tensor.

    The grayscale image is replicated to 3 channels via PIL convert('RGB'),
    matching the training pipeline. Output is a batch of size 1 ready for
    model forward pass.

    Args:
        image_path: Path to the source TIFF file.
        model_card: Validated ModelCard; provides image_size and normalisation.

    Returns:
        Tensor of shape (1, 3, image_size, image_size).

    Raises:
        PreprocessingError: If the file is missing, corrupt, or unsupported.
    """
    img = load_tiff(image_path)
    transform = build_eval_transform(model_card)

    try:
        tensor = transform(img)
    except Exception as exc:
        raise PreprocessingError(
            f"Transform failed for {image_path}: {exc}"
        ) from exc

    return tensor.unsqueeze(0)  # add batch dimension → (1, 3, H, W)
