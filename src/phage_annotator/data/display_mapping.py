"""Display mapping utilities for non-destructive brightness/contrast control."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, Iterable, Optional

import numpy as np


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
    sync_vmin : bool
        If True, vmin changes propagate to parent/linked modalities.
    sync_vmax : bool
        If True, vmax changes propagate to parent/linked modalities.
    sync_contrast : bool
        If True, all contrast changes (vmin/vmax/gamma/lut/invert) cascade.
    per_panel : dict[str, DisplayMapping]
        Panel-specific mapping overrides (frame/mean/support/std).
    per_image : dict[int, dict[str, DisplayMapping]]
        Per-image overrides keyed by image id, then panel id.
    """

    min_val: float
    max_val: float
    gamma: float = 1.0
    mode: str = "linear"
    lut: int = 0
    invert: bool = False
    sync_vmin: bool = False
    sync_vmax: bool = False
    sync_contrast: bool = False
    per_panel: Dict[str, "DisplayMapping"] = field(default_factory=dict)
    per_image: Dict[int, Dict[str, "DisplayMapping"]] = field(default_factory=dict)

    @property
    def vmin(self) -> float:
        """Backward-compatible alias for legacy display consumers."""
        return float(self.min_val)

    @vmin.setter
    def vmin(self, value: float) -> None:
        """Return the vmin value."""
        self.min_val = float(value)

    @property
    def vmax(self) -> float:
        """Backward-compatible alias for legacy display consumers."""
        return float(self.max_val)

    @vmax.setter
    def vmax(self, value: float) -> None:
        """Return the vmax value."""
        self.max_val = float(value)

    @property
    def lut_name(self) -> str:
        """Human-readable LUT token for legacy project metadata export."""
        return str(int(self.lut))

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
        return DisplayMapping(
            self.min_val,
            self.max_val,
            self.gamma,
            self.mode,
            self.lut,
            self.invert,
            self.sync_vmin,
            self.sync_vmax,
            self.sync_contrast,
        )

    def set_sync_rules(
        self, sync_vmin: bool = False, sync_vmax: bool = False, sync_contrast: bool = False
    ) -> None:
        """Configure which contrast attributes should propagate to linked panels.

        Parameters
        ----------
        sync_vmin : bool
            If True, vmin changes propagate when synced.
        sync_vmax : bool
            If True, vmax changes propagate when synced.
        sync_contrast : bool
            If True, all contrast changes (gamma/lut/invert) propagate when synced.
            When enabled, also enables vmin and vmax propagation.
        """
        self.sync_vmin = bool(sync_vmin)
        self.sync_vmax = bool(sync_vmax)
        # sync_contrast implies sync_vmin and sync_vmax
        if sync_contrast:
            self.sync_vmin = True
            self.sync_vmax = True
        self.sync_contrast = bool(sync_contrast)

    def is_sync_enabled(self) -> bool:
        """Return True if any sync rule is enabled."""
        return self.sync_vmin or self.sync_vmax or self.sync_contrast

    def sync_state_code(self) -> str:
        """Return a compact code representing which rules are enabled.

        Returns
        -------
        str
            One of: "NONE", "VMIN", "VMAX", "VMIN+VMAX", "CONTRAST"
        """
        if self.sync_contrast:
            return "CONTRAST"
        if self.sync_vmin and self.sync_vmax:
            return "VMIN+VMAX"
        if self.sync_vmin:
            return "VMIN"
        if self.sync_vmax:
            return "VMAX"
        return "NONE"

    def propagate_sync_updates(
        self, source_image_id: int, panel: str
    ) -> list[tuple[int, str]]:
        """Return list of (image_id, panel) that should receive sync updates.

        When a modality's display settings change, this method identifies which
        other modalities should receive the same update based on their sync rules.

        Parameters
        ----------
        source_image_id : int
            The image/modality ID that initiated the change.
        panel : str
            The panel type (e.g., "frame", "mean", "std", "support").

        Returns
        -------
        list[tuple[int, str]]
            List of (image_id, panel) tuples representing modalities that should
            receive the update. The source image is excluded to prevent circular
            syncing. Only targets with sync rules enabled are included.

        Notes
        -----
        The returned list includes any per-image mapping for the given panel that:
        - Is not the source image (to prevent circular updates)
        - Has at least one sync rule enabled (sync_vmin, sync_vmax, or sync_contrast)

        Examples
        --------
        >>> mapping = DisplayMapping(0.0, 1.0)
        >>> img1 = mapping.mapping_for(1, "frame")
        >>> img2 = mapping.mapping_for(2, "frame")
        >>> img2.set_sync_rules(sync_vmin=True)
        >>> targets = mapping.propagate_sync_updates(1, "frame")
        >>> assert (2, "frame") in targets
        """
        targets = []
        
        # Check all per-image mappings for this panel
        for image_id, panels_dict in self.per_image.items():
            # Skip the source image (prevent circular sync)
            if image_id == source_image_id:
                continue
            
            # Check if this image has the requested panel
            if panel not in panels_dict:
                continue
            
            image_panel_mapping = panels_dict[panel]
            
            # Include if any sync rule is enabled
            if image_panel_mapping.is_sync_enabled():
                targets.append((image_id, panel))
        
        return targets


def mapping_to_dict(mapping: DisplayMapping) -> dict:
    """Serialize a DisplayMapping (no recursive dicts)."""
    return {
        "min_val": float(mapping.min_val),
        "max_val": float(mapping.max_val),
        "gamma": float(mapping.gamma),
        "mode": mapping.mode,
        "lut": int(mapping.lut),
        "invert": bool(mapping.invert),
        "sync_vmin": bool(mapping.sync_vmin),
        "sync_vmax": bool(mapping.sync_vmax),
        "sync_contrast": bool(mapping.sync_contrast),
    }


def mapping_from_dict(data: dict, fallback: Optional[DisplayMapping] = None) -> DisplayMapping:
    """Deserialize a DisplayMapping."""
    if fallback is None:
        fallback = DisplayMapping(0.0, 1.0)
    mapping = DisplayMapping(
        float(
            data.get(
                "min_val",
                data.get("vmin", data.get("min", fallback.min_val)),
            )
        ),
        float(
            data.get(
                "max_val",
                data.get("vmax", data.get("max", fallback.max_val)),
            )
        ),
        float(data.get("gamma", fallback.gamma)),
        data.get("mode", fallback.mode),
        int(data.get("lut", fallback.lut)),
        bool(data.get("invert", fallback.invert)),
        bool(data.get("sync_vmin", fallback.sync_vmin)),
        bool(data.get("sync_vmax", fallback.sync_vmax)),
        bool(data.get("sync_contrast", fallback.sync_contrast)),
    )
    return mapping


from phage_annotator.data.display_norm import build_norm
