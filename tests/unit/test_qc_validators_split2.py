"""Split definitions from test_qc_validators.py."""

from __future__ import annotations

from dataclasses import dataclass
from typing import List

import numpy as np
import pytest

from phage_annotator.analysis.qc_validators import (
    DuplicateValidator,
    OutOfBoundsValidator,
    MissingLabelValidator,
    DensityClusterValidator,
    ImageArtifactValidator,
    PoissonConsistencyValidator,
    QCValidator,
    IssueSeverity,
    QCIssue,
)


from tests.unit.test_qc_validators_split1 import create_mock_keypoint, sample_keypoints, image_shape_2d

@pytest.mark.order(1)
class TestMissingLabelValidator:
    """Test missing label detection."""
    
    def test_detects_empty_label(self):
        """Test detection of empty/none labels."""
        keypoints = [
            create_mock_keypoint(100, 200, label="gene_a", annotation_id="ann_1"),
            create_mock_keypoint(150, 250, label="", annotation_id="ann_2"),  # Empty label
            create_mock_keypoint(200, 300, label=None, annotation_id="ann_3"),  # None label
        ]
        
        issues = MissingLabelValidator.find_missing_labels(
            keypoints, image_id="img_001"
        )
        
        assert len(issues) == 2
        assert all(i.severity == IssueSeverity.WARNING for i in issues)
    
    def test_allows_specific_labels(self):
        """Test that allowed labels are not flagged."""
        keypoints = [
            create_mock_keypoint(100, 200, label="gene_a", annotation_id="ann_1"),
            create_mock_keypoint(150, 250, label="unknown", annotation_id="ann_2"),
            create_mock_keypoint(200, 300, label="other", annotation_id="ann_3"),
        ]
        allowed_labels = ["gene_a", "gene_b", "unknown"]
        
        issues = MissingLabelValidator.find_missing_labels(
            keypoints,
            image_id="img_001",
            allowed_labels=allowed_labels,
        )
        
        # Only "other" should be flagged
        assert len(issues) == 1
        assert "ann_3" in issues[0].affected_annotation_ids
    
    def test_all_labeled(self):
        """Test when all annotations have labels."""
        keypoints = [
            create_mock_keypoint(100, 200, label="gene_a", annotation_id="ann_1"),
            create_mock_keypoint(150, 250, label="gene_b", annotation_id="ann_2"),
            create_mock_keypoint(200, 300, label="gene_c", annotation_id="ann_3"),
        ]
        
        issues = MissingLabelValidator.find_missing_labels(
            keypoints, image_id="img_001"
        )
        
        assert len(issues) == 0
    
    def test_whitespace_only_label(self):
        """Test that whitespace-only labels are treated as missing."""
        keypoints = [
            create_mock_keypoint(100, 200, label="   ", annotation_id="ann_1"),
            create_mock_keypoint(150, 250, label="\t", annotation_id="ann_2"),
        ]
        
        issues = MissingLabelValidator.find_missing_labels(
            keypoints, image_id="img_001"
        )
        
        assert len(issues) == 2

@pytest.mark.order(1)
class TestDensityClusterValidator:
    """Test density cluster detection."""
    
    def test_detects_high_density_clusters(self):
        """Test detection of high density clusters."""
        keypoints = [
            # Cluster 1: 5 annotations in small area
            create_mock_keypoint(100, 100, annotation_id="ann_1"),
            create_mock_keypoint(102, 102, annotation_id="ann_2"),
            create_mock_keypoint(101, 103, annotation_id="ann_3"),
            create_mock_keypoint(103, 101, annotation_id="ann_4"),
            create_mock_keypoint(102, 101, annotation_id="ann_5"),
            # Isolated
            create_mock_keypoint(500, 500, annotation_id="ann_6"),
        ]
        image_shape = (1024, 1024)
        
        issues = DensityClusterValidator.find_high_density_clusters(
            keypoints,
            image_id="img_001",
            image_shape=image_shape,
            grid_size=50,
            min_density=3,
        )
        
        # Should detect the cluster
        assert len(issues) >= 1
    
    def test_respects_density_threshold(self):
        """Test that minimum density is respected."""
        keypoints = [
            # Cluster with 3 annotations
            create_mock_keypoint(100, 100, annotation_id="ann_1"),
            create_mock_keypoint(102, 102, annotation_id="ann_2"),
            create_mock_keypoint(101, 103, annotation_id="ann_3"),
        ]
        image_shape = (1024, 1024)
        
        # Should detect with min_density=3
        issues = DensityClusterValidator.find_high_density_clusters(
            keypoints,
            image_id="img_001",
            image_shape=image_shape,
            min_density=3,
        )
        assert len(issues) == 1
        
        # Should not detect with min_density=4
        issues = DensityClusterValidator.find_high_density_clusters(
            keypoints,
            image_id="img_001",
            image_shape=image_shape,
            min_density=4,
        )
        assert len(issues) == 0
    
    def test_empty_regions(self):
        """Test when there are no high-density clusters."""
        keypoints = [
            create_mock_keypoint(100, 100, annotation_id="ann_1"),
            create_mock_keypoint(500, 500, annotation_id="ann_2"),
            create_mock_keypoint(900, 900, annotation_id="ann_3"),
        ]
        image_shape = (1024, 1024)
        
        issues = DensityClusterValidator.find_high_density_clusters(
            keypoints,
            image_id="img_001",
            image_shape=image_shape,
            min_density=3,
        )
        
        assert len(issues) == 0

@pytest.mark.order(2)
class TestQCValidator:
    """Test unified QC validator."""
    
    def test_orchestrates_all_validators(self, sample_keypoints, image_shape_2d):
        """Test that QCValidator runs all validator types."""
        # Add an out-of-bounds point
        sample_keypoints.append(create_mock_keypoint(-10, -10, annotation_id="ann_oob"))
        
        issues = QCValidator.validate(
            sample_keypoints,
            image_id="img_001",
            image_shape=image_shape_2d,
        )
        
        # Should have at least the out-of-bounds issue
        assert len(issues) >= 1
        issue_types = {i.issue_type for i in issues}
        assert "out_of_bounds" in issue_types
    
    def test_sorts_by_severity(self, sample_keypoints, image_shape_2d):
        """Test that issues are sorted by severity."""
        # Create issues of different severities
        sample_keypoints = [
            create_mock_keypoint(100, 100, label="", annotation_id="ann_1"),  # Missing label
            create_mock_keypoint(100, 100, annotation_id="ann_2"),  # Duplicate
            create_mock_keypoint(-10, -10, annotation_id="ann_3"),  # Out of bounds
        ]
        
        issues = QCValidator.validate(
            sample_keypoints,
            image_id="img_001",
            image_shape=image_shape_2d,
        )
        
        # Check that errors come before warnings
        if len(issues) > 1:
            severities = [i.severity for i in issues]
            error_indices = [i for i, s in enumerate(severities) if s == IssueSeverity.ERROR]
            warning_indices = [i for i, s in enumerate(severities) if s == IssueSeverity.WARNING]
            
            if error_indices and warning_indices:
                assert max(error_indices) < min(warning_indices)
    
    def test_sets_image_id(self, sample_keypoints, image_shape_2d):
        """Test that image_id is set on all issues."""
        sample_keypoints.append(create_mock_keypoint(-10, -10, annotation_id="ann_oob"))
        
        issues = QCValidator.validate(
            sample_keypoints,
            image_id="img_test_123",
            image_shape=image_shape_2d,
        )
        
        assert all(i.image_id == "img_test_123" for i in issues)
    
    def test_empty_issues(self):
        """Test when there are no issues."""
        keypoints = [
            create_mock_keypoint(100, 200, label="gene_a", annotation_id="ann_1"),
            create_mock_keypoint(500, 500, label="gene_b", annotation_id="ann_2"),
        ]
        image_shape = (1024, 1024)
        
        issues = QCValidator.validate(
            keypoints,
            image_id="img_001",
            image_shape=image_shape,
        )
        
        assert len(issues) == 0
    
    def test_multiple_issue_types(self, image_shape_2d):
        """Test validation with multiple different issue types."""
        keypoints = [
            # Duplicates
            create_mock_keypoint(100, 100, annotation_id="ann_1"),
            create_mock_keypoint(100, 100, annotation_id="ann_2"),
            # Out of bounds
            create_mock_keypoint(-10, -10, annotation_id="ann_3"),
            # Missing label
            create_mock_keypoint(300, 300, label="", annotation_id="ann_4"),
            # High density cluster
            create_mock_keypoint(500, 500, annotation_id="ann_5"),
            create_mock_keypoint(502, 502, annotation_id="ann_6"),
            create_mock_keypoint(501, 503, annotation_id="ann_7"),
            create_mock_keypoint(503, 501, annotation_id="ann_8"),
        ]
        
        issues = QCValidator.validate(
            keypoints,
            image_id="img_001",
            image_shape=image_shape_2d,
        )
        
        issue_types = {i.issue_type for i in issues}
        
        # Should detect at least duplicates and out_of_bounds
        assert "duplicate" in issue_types or "out_of_bounds" in issue_types
