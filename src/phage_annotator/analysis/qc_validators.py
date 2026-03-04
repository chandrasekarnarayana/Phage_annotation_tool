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

if TYPE_CHECKING:
    from phage_annotator.core.annotation import Keypoint
    from phage_annotator.session.qc_thresholds import QCThresholds


class IssueSeverity(Enum):
    """Severity level for QC issues."""
    INFO = "info"
    WARNING = "warning"
    ERROR = "error"


@dataclass
class QCIssue:
    """A quality control issue detected in annotations."""
    
    issue_id: str  # unique ID
    severity: IssueSeverity
    issue_type: str  # "duplicate", "out_of_bounds", "missing_label", "density_cluster"
    message: str
    image_id: int
    affected_annotation_ids: List[str] = field(default_factory=list)
    location_x: Optional[float] = None  # For click-to-jump
    location_y: Optional[float] = None
    location_z: Optional[int] = None
    location_t: Optional[int] = None
    
    def __str__(self) -> str:
        """Format issue as human-readable string."""
        return f"[{self.severity.value.upper()}] {self.issue_type}: {self.message}"


class DuplicateValidator:
    """Detects duplicate annotations (too close together)."""
    
    @staticmethod
    def find_duplicates(
        annotations: List["Keypoint"],
        image_id: str = "unknown",
        threshold: float = 2.0,
    ) -> List[QCIssue]:
        """Find annotations that are too close together.
        
        Parameters
        ----------
        annotations : list of Keypoint
            Annotations to check.
        image_id : str, default "unknown"
            Image ID for issue context.
        threshold : float, default 2.0
            Maximum distance for considering annotations as duplicates (in pixels).
        
        Returns
        -------
        list of QCIssue
            Duplicate issues found.
        """
        issues = []
        checked = set()
        
        for i, ann1 in enumerate(annotations):
            if ann1.annotation_id in checked:
                continue
            
            duplicates = [ann1]
            
            for j, ann2 in enumerate(annotations[i + 1 :], start=i + 1):
                if ann2.annotation_id in checked:
                    continue
                
                dx = ann1.x - ann2.x
                dy = ann1.y - ann2.y
                dist = (dx * dx + dy * dy) ** 0.5
                
                if dist < threshold:
                    duplicates.append(ann2)
                    checked.add(ann2.annotation_id)
            
            if len(duplicates) > 1:
                issue_id = f"dup_{duplicates[0].annotation_id}"
                ids = [a.annotation_id for a in duplicates]
                checked.add(ann1.annotation_id)
                
                issues.append(QCIssue(
                    issue_id=issue_id,
                    severity=IssueSeverity.ERROR,
                    issue_type="duplicate",
                    message=f"Found {len(duplicates)} annotations within {threshold}px: {', '.join(ids)}",
                    image_id=image_id,
                    affected_annotation_ids=ids,
                    location_x=duplicates[0].x,
                    location_y=duplicates[0].y,
                    location_z=getattr(duplicates[0], "z", 0),
                    location_t=getattr(duplicates[0], "t", 0),
                ))
        
        return issues


class OutOfBoundsValidator:
    """Detects annotations outside image bounds."""
    
    @staticmethod
    def find_out_of_bounds(
        annotations: List["Keypoint"],
        image_id: str = "unknown",
        image_shape: tuple = None,
        safety_margin: float = 0.0,
    ) -> List[QCIssue]:
        """Find annotations outside or near image boundaries.
        
        Parameters
        ----------
        annotations : list of Keypoint
            Annotations to check.
        image_id : str, default "unknown"
            Image ID for issue context.
        image_shape : tuple, optional
            (height, width) of image. If None, no bounds checking.
        safety_margin : float, default 0.0
            Safety margin (annotations within margin of edge flagged as warning).
        
        Returns
        -------
        list of QCIssue
            Out-of-bounds issues.
        """
        issues = []
        
        if image_shape is None:
            return issues
        
        image_height, image_width = image_shape
        
        for ann in annotations:
            out_of_bounds = False
            
            # Check bounds
            if ann.x < 0 or ann.x >= image_width or ann.y < 0 or ann.y >= image_height:
                out_of_bounds = True
                severity = IssueSeverity.ERROR
            elif (ann.x < safety_margin or ann.x >= image_width - safety_margin or 
                  ann.y < safety_margin or ann.y >= image_height - safety_margin):
                out_of_bounds = True
                severity = IssueSeverity.WARNING
            else:
                continue
            
            if out_of_bounds:
                issues.append(QCIssue(
                    issue_id=f"oob_{ann.annotation_id}",
                    severity=severity,
                    issue_type="out_of_bounds",
                    message=f"Annotation at ({ann.x:.1f}, {ann.y:.1f}) outside bounds (0-{image_width}, 0-{image_height})",
                    image_id=image_id,
                    affected_annotation_ids=[ann.annotation_id],
                    location_x=ann.x,
                    location_y=ann.y,
                    location_z=getattr(ann, "z", 0),
                    location_t=getattr(ann, "t", 0),
                ))
        
        return issues


class MissingLabelValidator:
    """Detects annotations with missing or inconsistent labels."""
    
    @staticmethod
    def find_missing_labels(
        annotations: List["Keypoint"],
        image_id: str = "unknown",
        allowed_labels: Optional[List[str]] = None,
    ) -> List[QCIssue]:
        """Find annotations with missing or invalid labels.
        
        Parameters
        ----------
        annotations : list of Keypoint
            Annotations to check.
        image_id : str, default "unknown"
            Image ID for issue context.
        allowed_labels : list of str, optional
            List of valid label names. If None, any non-empty label is OK.
        
        Returns
        -------
        list of QCIssue
            Missing label issues.
        """
        issues = []
        
        for ann in annotations:
            label = getattr(ann, "label", None)
            
            # Check if label is missing or empty (handle whitespace)
            if label is None or (isinstance(label, str) and not label.strip()):
                issues.append(QCIssue(
                    issue_id=f"missing_label_{ann.annotation_id}",
                    severity=IssueSeverity.WARNING,
                    issue_type="missing_label",
                    message=f"Annotation has no label",
                    image_id=image_id,
                    affected_annotation_ids=[ann.annotation_id],
                    location_x=getattr(ann, "x", None),
                    location_y=getattr(ann, "y", None),
                    location_z=getattr(ann, "z", 0),
                    location_t=getattr(ann, "t", 0),
                ))
            
            # Check if label is in allowed list
            elif allowed_labels and label not in allowed_labels:
                issues.append(QCIssue(
                    issue_id=f"invalid_label_{ann.annotation_id}",
                    severity=IssueSeverity.WARNING,
                    issue_type="missing_label",
                    message=f"Unknown label '{label}' (not in allowed list)",
                    image_id=image_id,
                    affected_annotation_ids=[ann.annotation_id],
                    location_x=getattr(ann, "x", None),
                    location_y=getattr(ann, "y", None),
                    location_z=getattr(ann, "z", 0),
                    location_t=getattr(ann, "t", 0),
                ))
        
        return issues


class DensityClusterValidator:
    """Detects suspicious density clusters."""
    
    @staticmethod
    def find_high_density_clusters(
        annotations: List["Keypoint"],
        image_id: str = "unknown",
        image_shape: tuple = None,
        grid_size: float = 50.0,
        min_density: int = 5,
    ) -> List[QCIssue]:
        """Find regions with unusually high annotation density.
        
        Parameters
        ----------
        annotations : list of Keypoint
            Annotations to check.
        image_id : str, default "unknown"
            Image ID for issue context.
        image_shape : tuple, optional
            (height, width) of image (not used for density check).
        grid_size : float, default 50.0
            Size of grid cells for clustering (in pixels).
        min_density : int, default 5
            Minimum annotations per cluster to flag as suspicious.
        
        Returns
        -------
        list of QCIssue
            High-density cluster issues.
        """
        issues = []
        
        if len(annotations) < min_density:
            return issues
        
        # Create grid and count annotations per cell
        cells = {}
        
        for ann in annotations:
            cell_x = int(ann.x // grid_size)
            cell_y = int(ann.y // grid_size)
            key = (cell_x, cell_y)
            
            if key not in cells:
                cells[key] = []
            cells[key].append(ann)
        
        # Check for high-density cells
        for (cell_x, cell_y), cell_annotations in cells.items():
            if len(cell_annotations) >= min_density:
                # Calculate actual mean position
                mean_x = np.mean([a.x for a in cell_annotations])
                mean_y = np.mean([a.y for a in cell_annotations])
                
                issues.append(QCIssue(
                    issue_id=f"density_cluster_{cell_x}_{cell_y}",
                    severity=IssueSeverity.INFO,
                    issue_type="density_cluster",
                    message=f"High-density cluster: {len(cell_annotations)} annotations in {grid_size}×{grid_size}px region",
                    image_id=image_id,
                    affected_annotation_ids=[a.annotation_id for a in cell_annotations],
                    location_x=mean_x,
                    location_y=mean_y,
                    location_z=getattr(cell_annotations[0], "z", 0),
                    location_t=getattr(cell_annotations[0], "t", 0),
                ))
        
        return issues


class ImageArtifactValidator:
    """Detect broad image/stack artifact patterns using fast heuristics."""

    @staticmethod
    def _prepare_frames(image_array: Optional[np.ndarray]) -> Optional[np.ndarray]:
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


class PoissonConsistencyValidator:
    """Poisson/Fano-factor checks for image signal and annotation stochasticity."""

    @staticmethod
    def find_image_signal_stochasticity(
        image_array: Optional[np.ndarray],
        image_id: str = "unknown",
    ) -> List[QCIssue]:
        frames = ImageArtifactValidator._prepare_frames(image_array)
        if frames is None:
            return []
        mean_frame = np.mean(frames, axis=0)
        values = mean_frame[np.isfinite(mean_frame)]
        if values.size < 64:
            return []
        values = values[values >= np.percentile(values, 5)]
        if values.size < 64:
            return []
        mu = float(np.mean(values))
        if mu <= 1e-6:
            return []
        fano = float(np.var(values) / max(mu, 1e-6))
        if 0.6 <= fano <= 1.8:
            return []
        severity = IssueSeverity.INFO if fano < 3.0 else IssueSeverity.WARNING
        h, w = mean_frame.shape
        return [
            QCIssue(
                issue_id=f"poisson_image_{image_id}",
                severity=severity,
                issue_type="image_stochasticity",
                message=(
                    "Image signal deviates from Poisson-like variability "
                    f"(Fano={fano:.2f})."
                ),
                image_id=image_id,
                location_x=float(w / 2.0),
                location_y=float(h / 2.0),
            )
        ]

    @staticmethod
    def find_annotation_stochasticity(
        annotations: List["Keypoint"],
        image_id: str = "unknown",
        image_shape: Optional[Tuple[int, int]] = None,
        grid_size: float = 64.0,
    ) -> List[QCIssue]:
        if image_shape is None or len(annotations) < 8:
            return []
        h, w = int(image_shape[0]), int(image_shape[1])
        if h <= 0 or w <= 0:
            return []
        gy = max(1, int(np.ceil(h / grid_size)))
        gx = max(1, int(np.ceil(w / grid_size)))
        counts = np.zeros((gy, gx), dtype=np.int32)
        valid = []
        for ann in annotations:
            x = float(getattr(ann, "x", -1.0))
            y = float(getattr(ann, "y", -1.0))
            if not (0 <= x < w and 0 <= y < h):
                continue
            iy = min(gy - 1, int(y // grid_size))
            ix = min(gx - 1, int(x // grid_size))
            counts[iy, ix] += 1
            valid.append(ann)
        if not valid:
            return []
        flat = counts.ravel().astype(np.float32)
        mu = float(np.mean(flat))
        if mu <= 1e-6:
            return []
        fano = float(np.var(flat) / mu)
        if 0.5 <= fano <= 2.5:
            return []
        severity = IssueSeverity.WARNING if fano > 2.5 else IssueSeverity.INFO
        first = valid[0]
        return [
            QCIssue(
                issue_id=f"poisson_ann_{image_id}",
                severity=severity,
                issue_type="annotation_stochasticity",
                message=(
                    "Annotation counts deviate from Poisson-like spatial distribution "
                    f"(Fano={fano:.2f})."
                ),
                image_id=image_id,
                affected_annotation_ids=[str(getattr(a, "annotation_id", "")) for a in valid],
                location_x=float(getattr(first, "x", 0.0)),
                location_y=float(getattr(first, "y", 0.0)),
                location_z=int(getattr(first, "z", 0)),
                location_t=int(getattr(first, "t", 0)),
            )
        ]


class QCValidator:
    """Unified QC validator that runs all checks."""
    
    @staticmethod
    def validate(
        annotations: List["Keypoint"],
        image_id: str = "unknown",
        image_shape: tuple = None,
        image_array: Optional[np.ndarray] = None,
        duplicate_threshold: Optional[float] = None,
        out_of_bounds_margin: Optional[float] = None,
        density_grid_size: Optional[float] = None,
        density_min_count: Optional[int] = None,
        allowed_labels: Optional[List[str]] = None,
        thresholds: Optional["QCThresholds"] = None,
    ) -> List[QCIssue]:
        """Run all QC checks.
        
        Parameters
        ----------
        annotations : list of Keypoint
            Annotations to validate.
        image_id : str, default "unknown"
            Image ID for issue context.
        image_shape : tuple, optional
            (height, width) of image.
        image_array : np.ndarray, optional
            Loaded image/stack array for artifact and stochasticity checks.
        duplicate_threshold : float, optional
            Distance threshold for duplicate detection. Uses thresholds config if None.
        out_of_bounds_margin : float, optional
            Safety margin for out-of-bounds detection. Uses thresholds config if None.
        density_grid_size : float, optional
            Grid size for density clustering. Uses thresholds config if None.
        density_min_count : int, optional
            Minimum annotations per cluster. Uses thresholds config if None.
        allowed_labels : list of str, optional
            Required label names.
        thresholds : QCThresholds, optional
            Threshold configuration. If None, uses defaults.
        
        Returns
        -------
        list of QCIssue
            All issues found, sorted by severity.
        """
        # Import here to avoid circular dependency
        if thresholds is None:
            from phage_annotator.session.qc_thresholds import get_default_thresholds
            thresholds = get_default_thresholds()
        
        # Use provided parameters or fall back to thresholds config
        dup_threshold = duplicate_threshold if duplicate_threshold is not None else thresholds.duplicate_distance_px
        oob_margin = out_of_bounds_margin if out_of_bounds_margin is not None else thresholds.border_safety_margin_px
        d_grid_size = density_grid_size if density_grid_size is not None else thresholds.density_grid_size_px
        d_min_count = density_min_count if density_min_count is not None else thresholds.density_min_annotations
        
        all_issues = []
        
        # Run validators only if enabled
        if thresholds.enabled_duplicate_check:
            all_issues.extend(
                DuplicateValidator.find_duplicates(
                    annotations,
                    image_id=image_id,
                    threshold=dup_threshold,
                )
            )
        
        if thresholds.enabled_bounds_check:
            all_issues.extend(
                OutOfBoundsValidator.find_out_of_bounds(
                    annotations,
                    image_id=image_id,
                    image_shape=image_shape,
                    safety_margin=oob_margin,
                )
            )
        
        if thresholds.enabled_label_check:
            all_issues.extend(
                MissingLabelValidator.find_missing_labels(
                    annotations,
                    image_id=image_id,
                    allowed_labels=allowed_labels,
                )
            )
        
        if thresholds.enabled_density_check:
            all_issues.extend(
                DensityClusterValidator.find_high_density_clusters(
                    annotations,
                    image_id=image_id,
                    image_shape=image_shape,
                    grid_size=d_grid_size,
                    min_density=d_min_count,
                )
            )

        if thresholds.enabled_illumination_check or thresholds.enabled_photobleaching_check or \
           thresholds.enabled_dust_check or thresholds.enabled_patterned_check or \
           thresholds.enabled_clustered_signal_check:
            all_issues.extend(
                ImageArtifactValidator.find_artifacts(
                    image_array=image_array,
                    image_id=image_id,
                )
            )

        if thresholds.enabled_image_fano_check:
            all_issues.extend(
                PoissonConsistencyValidator.find_image_signal_stochasticity(
                    image_array=image_array,
                    image_id=image_id,
                )
            )

        if thresholds.enabled_annotation_fano_check:
            all_issues.extend(
                PoissonConsistencyValidator.find_annotation_stochasticity(
                    annotations=annotations,
                    image_id=image_id,
                    image_shape=image_shape,
                )
            )
        
        # Sort by severity (ERROR > WARNING > INFO) then by type
        severity_order = {IssueSeverity.ERROR: 0, IssueSeverity.WARNING: 1, IssueSeverity.INFO: 2}
        all_issues.sort(key=lambda x: (severity_order[x.severity], x.issue_type))
        
        return all_issues
