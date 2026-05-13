"""Domain models and constants for classifier metadata."""

from dataclasses import dataclass
from typing import Optional

# Official RVL-CDIP 16-class label list in label-index order.
# This ordering is fixed by train.txt / val.txt / test.txt from aharley/rvl_cdip
# and must match the model's output logit indices exactly.
RVL_CDIP_LABELS: list[str] = [
    "letter",  # 0
    "form",  # 1
    "email",  # 2
    "handwritten",  # 3
    "advertisement",  # 4
    "scientific report",  # 5
    "scientific publication",  # 6
    "specification",  # 7
    "file folder",  # 8
    "news article",  # 9
    "budget",  # 10
    "invoice",  # 11
    "presentation",  # 12
    "questionnaire",  # 13
    "resume",  # 14
    "memo",  # 15
]

SUPPORTED_ARCHITECTURES: frozenset[str] = frozenset({"convnext_tiny", "convnext_small"})


@dataclass(frozen=True)
class ModelCardArtifact:
    """Classifier file location and integrity metadata."""

    sha256: str
    size_bytes: int
    path: str


@dataclass(frozen=True)
class ModelCardInput:
    """Expected input shape and normalisation for the model."""

    image_size: int
    channels: int
    normalization_mean: list[float]
    normalization_std: list[float]


@dataclass(frozen=True)
class ModelCardMetrics:
    """Evaluation metrics recorded at training time."""

    full_test_top1: float
    full_test_top5: float
    full_test_n: int


@dataclass(frozen=True)
class ModelCard:
    """Parsed and validated representation of model_card.json."""

    name: str
    version: str
    backbone: str
    num_classes: int
    classes: list[str]
    artifact: ModelCardArtifact
    input_config: ModelCardInput
    metrics: ModelCardMetrics
    refuse_to_start_threshold: float
    raw: dict  # original parsed JSON kept for forward-compatibility
