"""Presets for SMLM workflows (ThunderSTORM + Deep-STORM)."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Dict


@dataclass(frozen=True)
class ThunderPreset:
    """Parameter preset for the ThunderSTORM-style pipeline."""

    sigma_px: float
    fit_radius_px: int
    detection_thr_sigma: float
    merge_radius_px: float
    min_photons: float


@dataclass(frozen=True)
class DeepPreset:
    """Parameter preset for Deep-STORM inference."""

    patch_size: int
    overlap: int
    upsample: int
    sigma_px: float
    normalize_mode: str
    window_size: int
    aggregation_mode: str


PRESETS: Dict[str, Dict[str, object]] = {
    "Conservative": {
        "thunder": ThunderPreset(
            sigma_px=1.4,
            fit_radius_px=5,
            detection_thr_sigma=4.5,
            merge_radius_px=1.0,
            min_photons=120.0,
        ),
        "deep": DeepPreset(
            patch_size=64,
            overlap=16,
            upsample=8,
            sigma_px=1.4,
            normalize_mode="per_patch",
            window_size=5,
            aggregation_mode="mean",
        ),
    },
    "Balanced": {
        "thunder": ThunderPreset(
            sigma_px=1.3,
            fit_radius_px=4,
            detection_thr_sigma=3.0,
            merge_radius_px=1.0,
            min_photons=50.0,
        ),
        "deep": DeepPreset(
            patch_size=64,
            overlap=16,
            upsample=8,
            sigma_px=1.3,
            normalize_mode="per_patch",
            window_size=5,
            aggregation_mode="mean",
        ),
    },
    "Sensitive": {
        "thunder": ThunderPreset(
            sigma_px=1.2,
            fit_radius_px=3,
            detection_thr_sigma=2.2,
            merge_radius_px=1.0,
            min_photons=20.0,
        ),
        "deep": DeepPreset(
            patch_size=64,
            overlap=16,
            upsample=8,
            sigma_px=1.2,
            normalize_mode="per_patch",
            window_size=7,
            aggregation_mode="mean",
        ),
    },
}
