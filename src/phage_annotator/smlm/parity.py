"""Parity harness for comparing internal SMLM vs Fiji/ThunderSTORM outputs."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable, List, Sequence

import numpy as np

from phage_annotator.algorithms.smlm_thunderstorm import Localization


@dataclass(frozen=True)
class SmlmParityMetrics:
    """Summary metrics for localization parity."""

    internal_count: int
    bridge_count: int
    matched_count: int
    precision: float
    recall: float
    mean_xy_error_px: float
    median_xy_error_px: float


def compute_parity_metrics(
    internal: Sequence[Localization],
    bridge: Sequence[Localization],
    *,
    tolerance_px: float = 1.5,
) -> SmlmParityMetrics:
    """Compute frame-aware nearest-neighbor parity between two localization sets."""
    if tolerance_px <= 0:
        raise ValueError("tolerance_px must be positive.")
    internal_idx = _to_frame_arrays(internal)
    bridge_idx = _to_frame_arrays(bridge)
    matched = 0
    errors: List[float] = []
    for frame, a_pts in internal_idx.items():
        b_pts = bridge_idx.get(frame)
        if b_pts is None or b_pts.size == 0 or a_pts.size == 0:
            continue
        used = np.zeros((b_pts.shape[0],), dtype=bool)
        for point in a_pts:
            d = np.sqrt(np.sum((b_pts - point) ** 2, axis=1))
            if d.size == 0:
                continue
            j = int(np.argmin(d))
            if used[j]:
                continue
            err = float(d[j])
            if err <= tolerance_px:
                used[j] = True
                matched += 1
                errors.append(err)
    internal_count = len(internal)
    bridge_count = len(bridge)
    precision = float(matched / bridge_count) if bridge_count > 0 else 0.0
    recall = float(matched / internal_count) if internal_count > 0 else 0.0
    mean_err = float(np.mean(errors)) if errors else float("nan")
    median_err = float(np.median(errors)) if errors else float("nan")
    return SmlmParityMetrics(
        internal_count=internal_count,
        bridge_count=bridge_count,
        matched_count=matched,
        precision=precision,
        recall=recall,
        mean_xy_error_px=mean_err,
        median_xy_error_px=median_err,
    )


def _to_frame_arrays(locs: Iterable[Localization]) -> dict[int, np.ndarray]:
    """Convert frame arrays for the current workflow."""
    by_frame: dict[int, list[list[float]]] = {}
    for loc in locs:
        frame = int(getattr(loc, "frame_index", 0))
        by_frame.setdefault(frame, []).append(
            [float(getattr(loc, "x_px", 0.0)), float(getattr(loc, "y_px", 0.0))]
        )
    return {
        frame: np.asarray(points, dtype=np.float32)
        for frame, points in by_frame.items()
    }
