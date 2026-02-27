"""QC validators for annotation quality and problem detection.

Detects common annotation issues:
- Duplicate annotations (too close together)
- Out-of-bounds annotations
- Missing or inconsistent labels
- Suspicious density clusters
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Dict, List, Optional, Tuple, TYPE_CHECKING

import numpy as np

if TYPE_CHECKING:
    from phage_annotator.core.annotation import Keypoint


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


class QCValidator:
    """Unified QC validator that runs all checks."""
    
    @staticmethod
    def validate(
        annotations: List["Keypoint"],
        image_id: str = "unknown",
        image_shape: tuple = None,
        duplicate_threshold: float = 2.0,
        out_of_bounds_margin: float = 0.0,
        density_grid_size: float = 50.0,
        density_min_count: int = 5,
        allowed_labels: Optional[List[str]] = None,
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
        duplicate_threshold : float, default 2.0
            Distance threshold for duplicate detection.
        out_of_bounds_margin : float, default 0.0
            Safety margin for out-of-bounds detection.
        density_grid_size : float, default 50.0
            Grid size for density clustering.
        density_min_count : int, default 5
            Minimum annotations per cluster to flag.
        allowed_labels : list of str, optional
            Required label names.
        
        Returns
        -------
        list of QCIssue
            All issues found, sorted by severity.
        """
        all_issues = []
        
        # Run all validators
        all_issues.extend(
            DuplicateValidator.find_duplicates(
                annotations,
                image_id=image_id,
                threshold=duplicate_threshold,
            )
        )
        
        all_issues.extend(
            OutOfBoundsValidator.find_out_of_bounds(
                annotations,
                image_id=image_id,
                image_shape=image_shape,
                safety_margin=out_of_bounds_margin,
            )
        )
        
        all_issues.extend(
            MissingLabelValidator.find_missing_labels(
                annotations,
                image_id=image_id,
                allowed_labels=allowed_labels,
            )
        )
        
        all_issues.extend(
            DensityClusterValidator.find_high_density_clusters(
                annotations,
                image_id=image_id,
                image_shape=image_shape,
                grid_size=density_grid_size,
                min_density=density_min_count,
            )
        )
        
        # Sort by severity (ERROR > WARNING > INFO) then by type
        severity_order = {IssueSeverity.ERROR: 0, IssueSeverity.WARNING: 1, IssueSeverity.INFO: 2}
        all_issues.sort(key=lambda x: (severity_order[x.severity], x.issue_type))
        
        return all_issues
