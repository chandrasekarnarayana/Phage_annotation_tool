"""Display mapping utilities for non-destructive brightness/contrast control."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, Iterable, Optional

import numpy as np
from matplotlib import colors as mcolors


@dataclass
class DisplayMapping:
    """Brightness/contrast mapping state.

    Parameters
    ----------
    min_val, max_val : float
        Display window bounds in data units.
    gamma : float
        Gamma correction factor; 1.0 means linear.
    mode : {"linear", "log"}
        Display mapping mode.
    lut : int
        Colormap index for display.
    invert : bool
        Whether to display the LUT inverted.
    per_panel : dict[str, DisplayMapping]
        Panel-specific mapping overrides (frame/mean/composite/support/std).
    per_image : dict[int, dict[str, DisplayMapping]]
        Per-image overrides keyed by image id, then panel id.
    """

    min_val: float
    max_val: float
    gamma: float = 1.0
    mode: str = "linear"
    lut: int = 0
    invert: bool = False
    per_panel: Dict[str, "DisplayMapping"] = field(default_factory=dict)
    per_image: Dict[int, Dict[str, "DisplayMapping"]] = field(default_factory=dict)

    def set_window(self, min_val: float, max_val: float) -> None:
        """Set the display window bounds."""
        self.min_val = float(min_val)
        self.max_val = float(max_val)

    def shift(self, delta: float) -> None:
        """Shift window by a fixed delta (brightness)."""
        self.min_val += float(delta)
        self.max_val += float(delta)

    def scale(self, factor: float) -> None:
        """Scale window around its center (contrast)."""
        factor = float(factor)
        center = 0.5 * (self.min_val + self.max_val)
        half = 0.5 * (self.max_val - self.min_val) * factor
        self.min_val = center - half
        self.max_val = center + half

    def reset_to_full_range(self, min_val: float, max_val: float) -> None:
        """Reset window to full data range."""
        self.min_val = float(min_val)
        self.max_val = float(max_val)
        self.gamma = 1.0
        self.mode = "linear"

    def reset_to_auto(self, data: np.ndarray, low: float = 2.0, high: float = 98.0) -> None:
        """Reset window using percentile bounds."""
        if data.size == 0:
            return
        self.min_val = float(np.percentile(data, low))
        self.max_val = float(np.percentile(data, high))
        if self.min_val > self.max_val:
            self.min_val, self.max_val = self.max_val, self.min_val
        self.gamma = 1.0
        self.mode = "linear"

    def ensure_panels(self, panels: Iterable[str]) -> None:
        """Ensure per-panel mappings exist."""
        for panel in panels:
            self.per_panel.setdefault(panel, self.clone())

    def mapping_for(self, image_id: int, panel: str) -> "DisplayMapping":
        """Return the mapping for an image/panel, creating defaults as needed."""
        self.per_panel.setdefault(panel, self.clone())
        per_image = self.per_image.setdefault(image_id, {})
        per_image.setdefault(panel, self.per_panel[panel].clone())
        return per_image[panel]

    def clone(self) -> "DisplayMapping":
        """Return a shallow clone without per-panel/per-image dicts."""
        return DisplayMapping(self.min_val, self.max_val, self.gamma, self.mode, self.lut, self.invert)


def mapping_to_dict(mapping: DisplayMapping) -> dict:
    """Serialize a DisplayMapping (no recursive dicts)."""
    return {
        "min_val": float(mapping.min_val),
        "max_val": float(mapping.max_val),
        "gamma": float(mapping.gamma),
        "mode": mapping.mode,
        "lut": int(mapping.lut),
        "invert": bool(mapping.invert),
    }


def mapping_from_dict(data: dict, fallback: Optional[DisplayMapping] = None) -> DisplayMapping:
    """Deserialize a DisplayMapping."""
    if fallback is None:
        fallback = DisplayMapping(0.0, 1.0)
    return DisplayMapping(
        float(data.get("min_val", fallback.min_val)),
        float(data.get("max_val", fallback.max_val)),
        float(data.get("gamma", fallback.gamma)),
        data.get("mode", fallback.mode),
        int(data.get("lut", fallback.lut)),
        bool(data.get("invert", fallback.invert)),
    )


def build_norm(mapping: DisplayMapping) -> mcolors.Normalize:
    """Return a matplotlib normalization for the display mapping.

    Notes
    -----
    Gamma is applied via PowerNorm. Log mode uses a log1p transform so values
    at or below vmin remain stable and zero-safe.
    """
    vmin = float(mapping.min_val)
    vmax = float(mapping.max_val)
    if mapping.mode == "log":
        def _forward(x):
            return np.log1p(np.maximum(x - vmin, 0.0))

        def _inverse(y):
            return np.expm1(y) + vmin

        return mcolors.FuncNorm((_forward, _inverse), vmin=vmin, vmax=vmax)
    if mapping.gamma != 1.0:
        return mcolors.PowerNorm(gamma=mapping.gamma, vmin=vmin, vmax=vmax)
    return mcolors.Normalize(vmin=vmin, vmax=vmax)
