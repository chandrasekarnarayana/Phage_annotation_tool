"""QC validators for annotation quality and problem detection.

Detects common annotation issues:
- Duplicate annotations (too close together)
- Out-of-bounds annotations
- Missing or inconsistent labels
- Suspicious density clusters
- Image/stack artifacts (illumination, bleaching, patterned defects)
- Stochasticity deviations in image and annotation distributions
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Dict, List, Optional, Tuple, TYPE_CHECKING

import numpy as np

from phage_annotator.analysis.qc_issue_types import IssueSeverity, QCIssue

if TYPE_CHECKING:
    from phage_annotator.core.annotation import Keypoint
    from phage_annotator.session.qc_thresholds import QCThresholds





class ImageArtifactValidator:
    """Detect broad image/stack artifact patterns using fast heuristics."""

    @staticmethod
    def _prepare_frames(image_array: Optional[np.ndarray]) -> Optional[np.ndarray]:
        """Document the prepare_frames flow."""
        if image_array is None:
            return None
        arr = np.asarray(image_array, dtype=np.float32)
        if arr.size == 0 or arr.ndim < 2:
            return None

        if arr.ndim == 2:
            frames = arr[None, :, :]
        elif arr.ndim == 3:
            frames = arr
        else:
            # Prefer preserving leading temporal/slice dimensions and flattening them.
            h, w = int(arr.shape[-2]), int(arr.shape[-1])
            frames = arr.reshape(-1, h, w)

        # Cap workload while preserving coarse artifact patterns.
        max_frames = 32
        if frames.shape[0] > max_frames:
            idx = np.linspace(0, frames.shape[0] - 1, max_frames, dtype=int)
            frames = frames[idx]

        max_dim = 512
        h, w = int(frames.shape[1]), int(frames.shape[2])
        step_y = max(1, int(np.ceil(h / max_dim)))
        step_x = max(1, int(np.ceil(w / max_dim)))
        return frames[:, ::step_y, ::step_x]

    @staticmethod
    def find_artifacts(
        image_array: Optional[np.ndarray],
        image_id: str = "unknown",
    ) -> List[QCIssue]:
        """Detect common acquisition artifacts in image/stack data."""
        frames = ImageArtifactValidator._prepare_frames(image_array)
        if frames is None:
            return []

        issues: List[QCIssue] = []
        mean_frame = np.mean(frames, axis=0)
        h, w = int(mean_frame.shape[0]), int(mean_frame.shape[1])
        cx, cy = w / 2.0, h / 2.0
        eps = 1e-6

        # 1) Uneven illumination (center-vs-border bias).
        y0, y1 = h // 4, (3 * h) // 4
        x0, x1 = w // 4, (3 * w) // 4
        center = mean_frame[y0:y1, x0:x1]
        border_mask = np.ones_like(mean_frame, dtype=bool)
        border_mask[y0:y1, x0:x1] = False
        border = mean_frame[border_mask]
        if center.size > 0 and border.size > 0:
            ratio = float((np.mean(center) + eps) / (np.mean(border) + eps))
            if ratio > 1.25 or ratio < 0.80:
                issues.append(
                    QCIssue(
                        issue_id=f"illumination_{image_id}",
                        severity=IssueSeverity.WARNING,
                        issue_type="uneven_illumination",
                        message=(
                            f"Potential uneven illumination (center/border ratio={ratio:.2f})."
                        ),
                        image_id=image_id,
                        location_x=cx,
                        location_y=cy,
                    )
                )

        # 2) Photobleaching trend across frames.
        if frames.shape[0] >= 4:
            profile = np.mean(frames, axis=(1, 2))
            k = max(1, int(frames.shape[0] * 0.25))
            start_mean = float(np.mean(profile[:k]))
            end_mean = float(np.mean(profile[-k:]))
            drop = (start_mean - end_mean) / max(start_mean, eps)
            if drop > 0.15:
                issues.append(
                    QCIssue(
                        issue_id=f"bleach_{image_id}",
                        severity=IssueSeverity.WARNING,
                        issue_type="photobleaching",
                        message=f"Intensity decays over stack/time (drop={drop * 100.0:.1f}%).",
                        image_id=image_id,
                        location_x=cx,
                        location_y=cy,
                    )
                )

        # 3) Persistent dust/lens artifact pixels.
        if frames.shape[0] >= 3:
            var_map = np.var(frames, axis=0)
            low_var = var_map <= np.percentile(var_map, 10)
            p1 = np.percentile(mean_frame, 1)
            p99 = np.percentile(mean_frame, 99)
            persistent_extreme = low_var & ((mean_frame <= p1) | (mean_frame >= p99))
            artifact_pixels = int(np.count_nonzero(persistent_extreme))
            min_pixels = max(20, int(0.0005 * mean_frame.size))
            if artifact_pixels >= min_pixels:
                issues.append(
                    QCIssue(
                        issue_id=f"dust_lens_{image_id}",
                        severity=IssueSeverity.WARNING,
                        issue_type="dust_lens_artifact",
                        message=(
                            "Persistent extreme pixels detected across frames "
                            f"({artifact_pixels} px)."
                        ),
                        image_id=image_id,
                        location_x=cx,
                        location_y=cy,
                    )
                )

        # 4) Patterned bright/dark bands (row/column structure).
        row_mean = np.mean(mean_frame, axis=1)
        col_mean = np.mean(mean_frame, axis=0)
        denom = max(float(np.std(mean_frame)), eps)
        row_band_strength = float(np.std(row_mean) / denom)
        col_band_strength = float(np.std(col_mean) / denom)
        if row_band_strength > 0.18 or col_band_strength > 0.18:
            issues.append(
                QCIssue(
                    issue_id=f"pattern_band_{image_id}",
                    severity=IssueSeverity.INFO,
                    issue_type="patterned_intensity",
                    message=(
                        "Patterned bright/dark areas detected "
                        f"(row={row_band_strength:.2f}, col={col_band_strength:.2f})."
                    ),
                    image_id=image_id,
                    location_x=cx,
                    location_y=cy,
                )
            )

        # 5) Clustered bright signal concentration in image domain.
        bright_threshold = np.percentile(mean_frame, 99.5)
        bright_mask = mean_frame >= bright_threshold
        if np.any(bright_mask):
            gy, gx = 8, 8
            cell_h = max(1, h // gy)
            cell_w = max(1, w // gx)
            ys, xs = np.nonzero(bright_mask)
            cy_idx = np.clip(ys // cell_h, 0, gy - 1)
            cx_idx = np.clip(xs // cell_w, 0, gx - 1)
            bins = cy_idx * gx + cx_idx
            counts = np.bincount(bins, minlength=gy * gx)
            mean_count = float(np.mean(counts))
            peak_count = int(np.max(counts))
            if mean_count > 0 and peak_count > max(50, 4.0 * mean_count):
                issues.append(
                    QCIssue(
                        issue_id=f"clustered_signal_{image_id}",
                        severity=IssueSeverity.INFO,
                        issue_type="clustered_signal",
                        message=(
                            "Signal is strongly concentrated in a small spatial region "
                            f"(peak cell count={peak_count})."
                        ),
                        image_id=image_id,
                        location_x=cx,
                        location_y=cy,
                    )
                )

        return issues
