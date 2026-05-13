"""Generates annotated overlay PNGs for classified documents."""

import io
from dataclasses import dataclass
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

from app.classifier.inference import InferenceResult


@dataclass(frozen=True)
class OverlayResult:
    """In-memory PNG overlay ready for upload to MinIO."""

    png_bytes: bytes
    width: int
    height: int


class OverlayError(Exception):
    """Raised when overlay generation fails."""


# Banner height in pixels drawn at the top of the image.
_BANNER_HEIGHT = 48
_BANNER_COLOR = (30, 30, 30)  # dark background
_TEXT_COLOR = (255, 255, 255)  # white text
_HIGH_CONF_COLOR = (34, 197, 94)  # green for confidence >= 0.7
_LOW_CONF_COLOR = (251, 146, 60)  # orange for confidence < 0.7


def generate_overlay(
    source_image_path: Path,
    result: InferenceResult,
) -> OverlayResult:
    """Draw the prediction label and confidence onto the source image.

    The annotation is a banner at the top of the image showing:
      - Predicted RVL-CDIP class
      - Top-1 confidence percentage
      - Colour-coded confidence (green >= 0.7, orange < 0.7)

    Args:
        source_image_path: Path to the original TIFF.
        result: InferenceResult from run_inference.

    Returns:
        OverlayResult with PNG bytes and dimensions.

    Raises:
        OverlayError: If the image cannot be read or the PNG cannot be produced.
    """
    try:
        img = Image.open(source_image_path).convert("RGB")
    except Exception as exc:
        raise OverlayError(
            f"Cannot open source image {source_image_path}: {exc}"
        ) from exc

    w, h = img.size
    canvas_height = h + _BANNER_HEIGHT
    canvas = Image.new("RGB", (w, canvas_height), color=_BANNER_COLOR)
    canvas.paste(img, (0, _BANNER_HEIGHT))

    draw = ImageDraw.Draw(canvas)

    conf_pct = result.top1_confidence * 100
    conf_color = _HIGH_CONF_COLOR if result.top1_confidence >= 0.7 else _LOW_CONF_COLOR
    label_text = result.predicted_class.upper()
    conf_text = f"{conf_pct:.1f}%"

    # Attempt to use a basic font; fall back to PIL default if not available.
    try:
        font_label = ImageFont.truetype("DejaVuSans-Bold.ttf", size=20)
        font_conf = ImageFont.truetype("DejaVuSans.ttf", size=16)
    except (IOError, OSError):
        font_label = ImageFont.load_default()
        font_conf = font_label

    draw.text((12, 8), label_text, fill=_TEXT_COLOR, font=font_label)
    draw.text((w - 80, 12), conf_text, fill=conf_color, font=font_conf)

    try:
        buf = io.BytesIO()
        canvas.save(buf, format="PNG")
        png_bytes = buf.getvalue()
    except Exception as exc:
        raise OverlayError(f"Failed to encode overlay PNG: {exc}") from exc

    return OverlayResult(png_bytes=png_bytes, width=w, height=canvas_height)
