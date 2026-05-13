"""Golden-set replay test (T044).

Verifies the classifier produces deterministic output on the 50 fixture TIFFs.
This is the production reproducibility contract — if it fails, either the
model weights changed or the inference path is no longer deterministic.
"""

from pathlib import Path

import pytest

from app.classifier.golden_replay import print_report, run_golden_replay
from app.classifier.loader import load_classifier
from app.classifier.validation import validate_all

_MODELS_DIR = Path(__file__).parent.parent.parent / "app" / "classifier" / "models"
_CLASSIFIER_PATH = _MODELS_DIR / "classifier.pt"
_MODEL_CARD_PATH = _MODELS_DIR / "model_card.json"

_FIXTURES_DIR = Path(__file__).parent / "fixtures"
_GOLDEN_EXPECTED = Path(__file__).parent / "golden_expected.json"


@pytest.mark.golden
def test_golden_replay_all_fixtures_pass():
    """All 50 golden fixtures must reproduce their recorded prediction."""
    if not _CLASSIFIER_PATH.exists():
        pytest.skip("classifier.pt not available (Git LFS not fetched)")
    if not _GOLDEN_EXPECTED.exists():
        pytest.skip("golden_expected.json fixture missing")

    model_card = validate_all(_CLASSIFIER_PATH, _MODEL_CARD_PATH)
    model = load_classifier(_CLASSIFIER_PATH, model_card)

    report = run_golden_replay(
        model=model,
        model_card=model_card,
        fixtures_dir=_FIXTURES_DIR,
        golden_expected_path=_GOLDEN_EXPECTED,
    )

    print_report(report)
    assert report.success, (
        f"Golden replay failed: {report.failed}/{report.total} fixtures "
        f"did not match recorded predictions."
    )
