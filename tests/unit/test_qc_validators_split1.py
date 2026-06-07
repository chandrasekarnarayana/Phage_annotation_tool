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


@dataclass
class MockKeypoint:
    """Mock keypoint for testing."""
    x: float
    y: float
    z: int = 0
    t: int = 0
    label: str = "test"
    annotation_id: str = "ann_001"
    metadata: dict = None
    
    def __post_init__(self):
        """Normalize derived state after dataclass initialization."""
        if self.metadata is None:
            self.metadata = {}

def create_mock_keypoint(
    x: float,
    y: float,
    z: int = 0,
    t: int = 0,
    label: str = "test",
    annotation_id: str = "ann_001",
) -> MockKeypoint:
    """Create a mock keypoint."""
    return MockKeypoint(x=x, y=y, z=z, t=t, label=label, annotation_id=annotation_id)

@pytest.fixture
def sample_keypoints() -> List[MockKeypoint]:
    """Create sample keypoints for testing."""
    return [
        create_mock_keypoint(100, 200, annotation_id="ann_1"),
        create_mock_keypoint(150, 250, annotation_id="ann_2"),
        create_mock_keypoint(500, 500, annotation_id="ann_3"),
    ]

@pytest.fixture
def image_shape_2d() -> tuple:
    """Return 2D image shape (height, width)."""
    return (1024, 1024)

@pytest.mark.order(1)
class TestDuplicateValidator:
    """Test duplicate detection."""
    
    def test_finds_exact_duplicates(self):
        """Test detection of exact duplicate coordinates."""
        keypoints = [
            create_mock_keypoint(100, 200, annotation_id="ann_1"),
            create_mock_keypoint(100, 200, annotation_id="ann_2"),  # Exact duplicate
        ]
        
        issues = DuplicateValidator.find_duplicates(keypoints, image_id="img_001")
        
        assert len(issues) == 1
        assert issues[0].severity == IssueSeverity.ERROR
        assert "ann_1" in issues[0].affected_annotation_ids
        assert "ann_2" in issues[0].affected_annotation_ids
    
    def test_finds_close_duplicates(self):
        """Test detection of nearly-duplicate coordinates."""
        keypoints = [
            create_mock_keypoint(100, 200, annotation_id="ann_1"),
            create_mock_keypoint(101, 201, annotation_id="ann_2"),  # ~1.4px away
        ]
        
        issues = DuplicateValidator.find_duplicates(
            keypoints, image_id="img_001", threshold=2.0
        )
        
        assert len(issues) == 1
    
    def test_respects_threshold(self):
        """Test that threshold parameter is respected."""
        keypoints = [
            create_mock_keypoint(100, 200, annotation_id="ann_1"),
            create_mock_keypoint(105, 200, annotation_id="ann_2"),  # 5px away
        ]
        
        # Should find with threshold=5.1
        issues = DuplicateValidator.find_duplicates(
            keypoints, image_id="img_001", threshold=5.1
        )
        assert len(issues) == 1
        
        # Should not find with threshold=4.9
        issues = DuplicateValidator.find_duplicates(
            keypoints, image_id="img_001", threshold=4.9
        )
        assert len(issues) == 0
    
    def test_no_duplicates(self):
        """Test when no duplicates exist."""
        keypoints = [
            create_mock_keypoint(100, 200, annotation_id="ann_1"),
            create_mock_keypoint(500, 500, annotation_id="ann_2"),
            create_mock_keypoint(900, 900, annotation_id="ann_3"),
        ]
        
        issues = DuplicateValidator.find_duplicates(keypoints, image_id="img_001")
        
        assert len(issues) == 0
    
    def test_multiple_duplicate_groups(self):
        """Test detection of multiple separate duplicate clusters."""
        keypoints = [
            create_mock_keypoint(100, 200, annotation_id="ann_1"),
            create_mock_keypoint(100, 200, annotation_id="ann_2"),  # Group 1
            create_mock_keypoint(500, 500, annotation_id="ann_3"),
            create_mock_keypoint(500, 500, annotation_id="ann_4"),  # Group 2
        ]
        
        issues = DuplicateValidator.find_duplicates(keypoints, image_id="img_001")
        
        # Should detect 2 duplicate groups
        assert len(issues) >= 1
    
    def test_empty_keypoints(self):
        """Test with no keypoints."""
        issues = DuplicateValidator.find_duplicates([], image_id="img_001")
        assert len(issues) == 0
    
    def test_single_keypoint(self):
        """Test with single keypoint."""
        keypoints = [create_mock_keypoint(100, 200, annotation_id="ann_1")]
        
        issues = DuplicateValidator.find_duplicates(keypoints, image_id="img_001")
        assert len(issues) == 0

@pytest.mark.order(1)
class TestOutOfBoundsValidator:
    """Test out-of-bounds detection."""
    
    def test_detects_out_of_bounds(self):
        """Test detection of annotations outside image bounds."""
        keypoints = [
            create_mock_keypoint(100, 200, annotation_id="ann_1"),
            create_mock_keypoint(2000, 2000, annotation_id="ann_2"),  # Out of bounds
        ]
        image_shape = (1024, 1024)
        
        issues = OutOfBoundsValidator.find_out_of_bounds(
            keypoints, image_id="img_001", image_shape=image_shape
        )
        
        assert len(issues) == 1
        assert issues[0].severity == IssueSeverity.ERROR
        assert "ann_2" in issues[0].affected_annotation_ids
    
    def test_respects_safety_margin(self):
        """Test that safety margin is applied."""
        keypoints = [
            create_mock_keypoint(10, 10, annotation_id="ann_1"),  # 10px from edge
        ]
        image_shape = (1024, 1024)
        
        # Should detect with 20px margin
        issues = OutOfBoundsValidator.find_out_of_bounds(
            keypoints,
            image_id="img_001",
            image_shape=image_shape,
            safety_margin=20,
        )
        assert len(issues) == 1
        
        # Should not detect with 5px margin
        issues = OutOfBoundsValidator.find_out_of_bounds(
            keypoints,
            image_id="img_001",
            image_shape=image_shape,
            safety_margin=5,
        )
        assert len(issues) == 0
    
    def test_negative_coordinates(self):
        """Test detection of negative coordinates."""
        keypoints = [
            create_mock_keypoint(-10, 200, annotation_id="ann_1"),
            create_mock_keypoint(100, -50, annotation_id="ann_2"),
        ]
        image_shape = (1024, 1024)
        
        issues = OutOfBoundsValidator.find_out_of_bounds(
            keypoints, image_id="img_001", image_shape=image_shape
        )
        
        assert len(issues) == 2
    
    def test_all_in_bounds(self):
        """Test when all annotations are in bounds."""
        keypoints = [
            create_mock_keypoint(100, 200, annotation_id="ann_1"),
            create_mock_keypoint(500, 500, annotation_id="ann_2"),
            create_mock_keypoint(1000, 1000, annotation_id="ann_3"),
        ]
        image_shape = (1024, 1024)
        
        issues = OutOfBoundsValidator.find_out_of_bounds(
            keypoints, image_id="img_001", image_shape=image_shape
        )
        
        assert len(issues) == 0
    
    def test_boundary_conditions(self):
        """Test exact boundary coordinates."""
        keypoints = [
            create_mock_keypoint(0, 0, annotation_id="ann_1"),  # Top-left corner
            create_mock_keypoint(1023, 1023, annotation_id="ann_2"),  # Bottom-right corner
            create_mock_keypoint(1024, 1024, annotation_id="ann_3"),  # Just outside
        ]
        image_shape = (1024, 1024)
        
        issues = OutOfBoundsValidator.find_out_of_bounds(
            keypoints, image_id="img_001", image_shape=image_shape
        )
        
        # Only ann_3 should be out of bounds
        assert len(issues) == 1
        assert "ann_3" in issues[0].affected_annotation_ids
