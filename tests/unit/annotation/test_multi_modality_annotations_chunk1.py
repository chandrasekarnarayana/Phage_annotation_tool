"""Split chunk from test_multi_modality_annotations.py."""


from __future__ import annotations

import pytest

from phage_annotator.core.annotation import Keypoint
from phage_annotator.core.multi_modality import (
    filter_by_modality,
    propagate_to_modality,
    assign_to_modality,
    get_modality_summary,
)


# ============================================================================
# Fixtures
# ============================================================================


@pytest.fixture
def sample_keypoints():
    """Create sample keypoints with various modality assignments."""
    return [
        # Modality 0 annotations
        Keypoint(image_id=0, image_name="img1.tif", t=0, z=0, y=10.0, x=20.0, label="phage", modality_idx=0),
        Keypoint(image_id=0, image_name="img1.tif", t=1, z=0, y=15.0, x=25.0, label="phage", modality_idx=0),
        # Modality 1 annotations
        Keypoint(image_id=0, image_name="img1.tif", t=0, z=0, y=30.0, x=40.0, label="phage", modality_idx=1),
        Keypoint(image_id=0, image_name="img1.tif", t=2, z=0, y=35.0, x=45.0, label="phage", modality_idx=1),
        # Global annotations (visible on all modalities)
        Keypoint(image_id=0, image_name="img1.tif", t=0, z=0, y=50.0, x=60.0, label="reference", modality_idx=None),
        Keypoint(image_id=0, image_name="img1.tif", t=1, z=0, y=55.0, x=65.0, label="reference", modality_idx=None),
    ]

class TestFilterByModality:
    """Test annotation filtering by modality."""

    def test_filter_modality_0_includes_global(self, sample_keypoints):
        """Test filtering for modality 0 includes global annotations."""
        filtered = filter_by_modality(sample_keypoints, modality_idx=0, show_all=True)
        
        # Should include: 2 modality-0 + 2 global = 4
        assert len(filtered) == 4
        modality_indices = {kp.modality_idx for kp in filtered}
        assert modality_indices == {0, None}

    def test_filter_modality_1_includes_global(self, sample_keypoints):
        """Test filtering for modality 1 includes global annotations."""
        filtered = filter_by_modality(sample_keypoints, modality_idx=1, show_all=True)
        
        # Should include: 2 modality-1 + 2 global = 4
        assert len(filtered) == 4
        modality_indices = {kp.modality_idx for kp in filtered}
        assert modality_indices == {1, None}

    def test_filter_modality_0_excludes_global(self, sample_keypoints):
        """Test filtering for modality 0 without global annotations."""
        filtered = filter_by_modality(sample_keypoints, modality_idx=0, show_all=False)
        
        # Should include: only 2 modality-0
        assert len(filtered) == 2
        assert all(kp.modality_idx == 0 for kp in filtered)

    def test_filter_modality_1_excludes_global(self, sample_keypoints):
        """Test filtering for modality 1 without global annotations."""
        filtered = filter_by_modality(sample_keypoints, modality_idx=1, show_all=False)
        
        # Should include: only 2 modality-1
        assert len(filtered) == 2
        assert all(kp.modality_idx == 1 for kp in filtered)

    def test_filter_none_returns_all(self, sample_keypoints):
        """Test filtering with None returns all annotations."""
        filtered = filter_by_modality(sample_keypoints, modality_idx=None)
        
        assert len(filtered) == len(sample_keypoints)
        assert filtered == sample_keypoints

    def test_filter_nonexistent_modality_returns_global_only(self, sample_keypoints):
        """Test filtering for non-existent modality returns only global."""
        filtered = filter_by_modality(sample_keypoints, modality_idx=99, show_all=True)
        
        # Should include: only 2 global
        assert len(filtered) == 2
        assert all(kp.modality_idx is None for kp in filtered)

    def test_filter_nonexistent_modality_excludes_global(self, sample_keypoints):
        """Test filtering for non-existent modality without global returns empty."""
        filtered = filter_by_modality(sample_keypoints, modality_idx=99, show_all=False)
        
        assert len(filtered) == 0

    def test_filter_empty_list(self):
        """Test filtering empty list returns empty."""
        filtered = filter_by_modality([], modality_idx=0)
        assert filtered == []

class TestPropagateToModality:
    """Test annotation propagation across modalities."""

    def test_propagate_modality_0_to_1(self, sample_keypoints):
        """Test propagating modality 0 annotations to modality 1."""
        # Get only modality 0 annotations
        modality_0 = [kp for kp in sample_keypoints if kp.modality_idx == 0]
        
        # Propagate to modality 1
        propagated = propagate_to_modality(modality_0, target_modality_idx=1)
        
        assert len(propagated) == 2
        assert all(kp.modality_idx == 1 for kp in propagated)
        
        # Check coordinates are preserved
        assert propagated[0].y == 10.0
        assert propagated[0].x == 20.0
        assert propagated[1].y == 15.0
        assert propagated[1].x == 25.0

    def test_propagate_creates_new_ids(self, sample_keypoints):
        """Test propagation creates new unique annotation IDs."""
        modality_0 = [kp for kp in sample_keypoints if kp.modality_idx == 0]
        original_ids = {kp.annotation_id for kp in modality_0}
        
        propagated = propagate_to_modality(modality_0, target_modality_idx=1)
        propagated_ids = {kp.annotation_id for kp in propagated}
        
        # IDs should be completely different
        assert len(original_ids & propagated_ids) == 0

    def test_propagate_updates_source(self, sample_keypoints):
        """Test propagation updates source field."""
        modality_0 = [kp for kp in sample_keypoints if kp.modality_idx == 0]
        
        propagated = propagate_to_modality(modality_0, target_modality_idx=1)
        
        assert all("propagated_from_modality_0" in kp.source for kp in propagated)

    def test_propagate_preserves_label(self, sample_keypoints):
        """Test propagation preserves labels."""
        modality_0 = [kp for kp in sample_keypoints if kp.modality_idx == 0]
        
        propagated = propagate_to_modality(modality_0, target_modality_idx=1)
        
        assert propagated[0].label == "phage"
        assert propagated[1].label == "phage"

    def test_propagate_empty_list(self):
        """Test propagating empty list returns empty."""
        propagated = propagate_to_modality([], target_modality_idx=1)
        assert propagated == []

    def test_propagate_global_to_specific(self, sample_keypoints):
        """Test propagating global annotations to specific modality."""
        global_annots = [kp for kp in sample_keypoints if kp.modality_idx is None]
        
        propagated = propagate_to_modality(global_annots, target_modality_idx=2)
        
        assert len(propagated) == 2
        assert all(kp.modality_idx == 2 for kp in propagated)
