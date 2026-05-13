"""Golden-set replay: verifies deterministic classifier behaviour against fixtures."""

import json
from dataclasses import dataclass
from pathlib import Path

import torch
import torch.nn as nn

from app.classifier.preprocessing import build_eval_transform, load_tiff
from app.domain.model_metadata import ModelCard


@dataclass
class GoldenResult:
    """Outcome of a single golden-set fixture check."""

    filename: str
    expected_label: int  # model_predicted_label from golden_expected.json
    expected_class: str
    expected_confidence: float
    actual_label: int
    actual_class: str
    actual_confidence: float
    passed: bool
    failure_reason: str  # empty string when passed


@dataclass
class ReplayReport:
    """Aggregated result of a full golden-set replay run."""

    total: int
    passed: int
    failed: int
    results: list[GoldenResult]

    @property
    def success(self) -> bool:
        return self.failed == 0


# Tolerance for confidence comparison, matching the notebook contract.
_CONFIDENCE_TOLERANCE = 1e-6


def run_golden_replay(
    model: nn.Module,
    model_card: ModelCard,
    fixtures_dir: Path,
    golden_expected_path: Path,
) -> ReplayReport:
    """Run all golden-set fixtures and return a ReplayReport.

    Each fixture is checked for:
      1. argmax(logits) == entry['model_predicted_label']
      2. top-1 confidence within 1e-6 of entry['expected_top1_confidence']

    Inference runs on CPU in float32 with no AMP, ensuring determinism
    across environments. This matches the docker production environment.

    Args:
        model: Loaded model in eval mode (from loader.load_classifier).
        model_card: Validated ModelCard for transform settings.
        fixtures_dir: Directory containing the 50 golden TIFF files.
        golden_expected_path: Path to golden_expected.json.

    Returns:
        ReplayReport with per-fixture results and overall pass/fail.
    """
    if not golden_expected_path.exists():
        raise FileNotFoundError(
            f"golden_expected.json not found: {golden_expected_path}"
        )

    with open(golden_expected_path) as f:
        entries = json.load(f)

    transform = build_eval_transform(model_card)
    model.eval()
    results: list[GoldenResult] = []

    for entry in entries:
        filename = entry["filename"]
        expected_label = int(entry["model_predicted_label"])
        expected_class = entry["model_predicted_class"]
        expected_conf = float(entry["expected_top1_confidence"])

        img_path = fixtures_dir / filename
        failure_reason = ""
        actual_label = -1
        actual_class = ""
        actual_conf = 0.0
        passed = False

        try:
            img = load_tiff(img_path)
            tensor = transform(img).unsqueeze(0).float()  # CPU float32

            with torch.no_grad():
                logits = model(tensor)

            probs = torch.softmax(logits, dim=1)[0]
            actual_label = int(probs.argmax().item())
            actual_conf = float(probs[actual_label].item())
            actual_class = model_card.classes[actual_label]

            label_ok = actual_label == expected_label
            conf_ok = abs(actual_conf - expected_conf) <= _CONFIDENCE_TOLERANCE

            if label_ok and conf_ok:
                passed = True
            else:
                parts = []
                if not label_ok:
                    parts.append(
                        f"label mismatch: expected {expected_label} "
                        f"({expected_class}), got {actual_label} ({actual_class})"
                    )
                if not conf_ok:
                    parts.append(
                        f"confidence mismatch: expected {expected_conf:.8f}, "
                        f"got {actual_conf:.8f} "
                        f"(diff={abs(actual_conf - expected_conf):.2e})"
                    )
                failure_reason = "; ".join(parts)

        except Exception as exc:
            failure_reason = f"exception: {exc}"

        results.append(
            GoldenResult(
                filename=filename,
                expected_label=expected_label,
                expected_class=expected_class,
                expected_confidence=expected_conf,
                actual_label=actual_label,
                actual_class=actual_class,
                actual_confidence=actual_conf,
                passed=passed,
                failure_reason=failure_reason,
            )
        )

    passed_count = sum(1 for r in results if r.passed)
    return ReplayReport(
        total=len(results),
        passed=passed_count,
        failed=len(results) - passed_count,
        results=results,
    )


def print_report(report: ReplayReport) -> None:
    """Print a CI-readable pass/fail summary to stdout."""
    print(f"\n{'='*60}")
    print(f"Golden-set replay: {report.passed}/{report.total} passed")
    print(f"{'='*60}")

    for r in report.results:
        status = "PASS" if r.passed else "FAIL"
        print(f"  [{status}] {r.filename}")
        if not r.passed:
            print(f"         {r.failure_reason}")

    print(f"\nResult: {'PASSED' if report.success else 'FAILED'}")
    print(f"{'='*60}\n")
