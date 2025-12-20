"""Configuration dataclasses for density prediction models."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class DensityConfig:
    """Normalization and output settings for density prediction.

    Notes
    -----
    The predicted density map can be integrated to a count using:
    ``count = density.sum() * count_scale``.
    """

    input_mode: str = "grayscale"
    normalize: str = "percentile"
    p_low: float = 1.0
    p_high: float = 99.0
    invert: bool = False
    expected_channels: int = 1
    model_output_scale: float = 1.0
    count_scale: float = 1.0
    threshold_clip_min: float = 0.0
    use_amp: bool = True
