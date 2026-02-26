"""Scale bar geometry helpers for rendering."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, Optional, Tuple


@dataclass(frozen=True)
class ScaleBarSpec:
    """Configuration for a scale bar overlay."""

    enabled: bool
    length_um: float
    thickness_px: int
    location: str
    padding_px: int
    show_text: bool
    text_offset_px: int
    background_box: bool
    text_format: str = ""


def compute_scalebar(
    extent: Tuple[float, float, float, float],
    pixel_size_um_per_px: Optional[float],
    spec: ScaleBarSpec,
) -> Optional[Dict[str, object]]:
    """Compute scale bar geometry in data coordinates."""
    if not spec.enabled or not pixel_size_um_per_px:
        return None
    if pixel_size_um_per_px <= 0:
        return None
    length_px = int(round(spec.length_um / pixel_size_um_per_px))
    if length_px <= 0:
        return None
    x0, x1, y0, y1 = extent
    x_min, x_max = (x0, x1) if x0 <= x1 else (x1, x0)
    y_min, y_max = (y0, y1) if y0 <= y1 else (y1, y0)
    left = x_min + spec.padding_px
    right = x_max - spec.padding_px - length_px
    top = y_min + spec.padding_px
    bottom = y_max - spec.padding_px - spec.thickness_px
    loc = spec.location.lower()
    if loc == "bottom_left":
        x = left
        y = bottom
    elif loc == "top_right":
        x = right
        y = top
    elif loc == "top_left":
        x = left
        y = top
    else:
        x = right
        y = bottom
    text = None
    text_pos = None
    if spec.show_text:
        text = spec.text_format.strip() if spec.text_format else _default_text(spec.length_um)
        text_pos = _text_position(x, y, length_px, spec.thickness_px, spec.text_offset_px, loc)
    return {
        "rect": (x, y, length_px, spec.thickness_px),
        "text": text,
        "text_pos": text_pos,
    }


def _default_text(length_um: float) -> str:
    return f"{length_um:g} um"


def _text_position(
    x: float, y: float, length_px: int, thickness_px: int, offset_px: int, loc: str
) -> Tuple[float, float]:
    if loc.startswith("top"):
        return (x + length_px / 2, y - offset_px)
    return (x + length_px / 2, y + thickness_px + offset_px)
