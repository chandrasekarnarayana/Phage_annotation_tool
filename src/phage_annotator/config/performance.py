"""Performance service level objectives (SLOs) for baseline datasets."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class PerformanceSLO:
    """Targets for navigation and redraw latency on reference datasets."""

    frame_step_p50_ms: int = 50
    frame_step_p95_ms: int = 150
    z_step_p50_ms: int = 50
    z_step_p95_ms: int = 150
    redraw_p50_ms: int = 60
    redraw_p95_ms: int = 200
    overlay_p95_ms: int = 250


REFERENCE_DATASET = {
    "description": "16-bit OME-TIFF, 2048x2048, T=200, Z=20",
    "bit_depth": 16,
    "shape": (200, 20, 2048, 2048),
    "channels": 1,
}

# Memory pressure thresholds for channel-aware sampling fallback
MEMORY_THRESHOLD_BYTES = 1.5e9  # 1.5 GB threshold for interactive loading
DOWNSAMPLE_FACTOR_FOR_PRESSURE = 2  # Apply 2x downsampling if memory pressure detected
MEMORY_PRESSURE_HYSTERESIS = 0.2  # Require 20% under threshold to resume loading full-res


DEFAULT_SLO = PerformanceSLO()
