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

from phage_annotator.analysis.qc_density_validators import (
    DensityClusterValidator,
    PoissonConsistencyValidator,
)
from phage_annotator.analysis.qc_image_validators import ImageArtifactValidator
from phage_annotator.analysis.qc_issue_types import (
    DuplicateValidator,
    IssueSeverity,
    MissingLabelValidator,
    OutOfBoundsValidator,
    QCIssue,
)

if TYPE_CHECKING:
    from phage_annotator.core.annotation import Keypoint
    from phage_annotator.session.qc_thresholds import QCThresholds





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
