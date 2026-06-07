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
from phage_annotator.analysis.qc_image_validators import ImageArtifactValidator

if TYPE_CHECKING:
    from phage_annotator.core.annotation import Keypoint
    from phage_annotator.session.qc_thresholds import QCThresholds





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



class PoissonConsistencyValidator:
    """Poisson/Fano-factor checks for image signal and annotation stochasticity."""

    @staticmethod
    def find_image_signal_stochasticity(
        image_array: Optional[np.ndarray],
        image_id: str = "unknown",
    ) -> List[QCIssue]:
        """Document the find_image_signal_stochasticity flow."""
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
        """Document the find_annotation_stochasticity flow."""
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
