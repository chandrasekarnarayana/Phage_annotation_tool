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


from tests.unit.annotation.test_multi_modality_annotations_chunk1 import sample_keypoints

class TestAssignToModality:
    """Test modality assignment."""

    def test_assign_to_modality_0(self):
        """Test assigning annotations to modality 0."""
        kps = [
            Keypoint(image_id=0, image_name="img.tif", t=0, z=0, y=10.0, x=20.0, modality_idx=None),
            Keypoint(image_id=0, image_name="img.tif", t=1, z=0, y=15.0, x=25.0, modality_idx=None),
        ]
        
        result = assign_to_modality(kps, modality_idx=0)
        
        assert result is kps  # Same list (in-place)
        assert all(kp.modality_idx == 0 for kp in kps)

    def test_assign_to_global(self):
        """Test assigning annotations to global (None)."""
        kps = [
            Keypoint(image_id=0, image_name="img.tif", t=0, z=0, y=10.0, x=20.0, modality_idx=0),
            Keypoint(image_id=0, image_name="img.tif", t=1, z=0, y=15.0, x=25.0, modality_idx=1),
        ]
        
        assign_to_modality(kps, modality_idx=None)
        
        assert all(kp.modality_idx is None for kp in kps)

    def test_assign_empty_list(self):
        """Test assigning empty list."""
        result = assign_to_modality([], modality_idx=0)
        assert result == []

    def test_assign_overwrites_existing(self):
        """Test assignment overwrites existing modality."""
        kps = [Keypoint(image_id=0, image_name="img.tif", t=0, z=0, y=10.0, x=20.0, modality_idx=0)]
        
        assign_to_modality(kps, modality_idx=1)
        
        assert kps[0].modality_idx == 1

class TestGetModalitySummary:
    """Test modality summary statistics."""

    def test_summary_multiple_modalities(self, sample_keypoints):
        """Test summary with multiple modalities."""
        summary = get_modality_summary(sample_keypoints)
        
        assert summary == {0: 2, 1: 2, None: 2}

    def test_summary_single_modality(self):
        """Test summary with single modality."""
        kps = [
            Keypoint(image_id=0, image_name="img.tif", t=0, z=0, y=10.0, x=20.0, modality_idx=0),
            Keypoint(image_id=0, image_name="img.tif", t=1, z=0, y=15.0, x=25.0, modality_idx=0),
            Keypoint(image_id=0, image_name="img.tif", t=2, z=0, y=20.0, x=30.0, modality_idx=0),
        ]
        
        summary = get_modality_summary(kps)
        
        assert summary == {0: 3}

    def test_summary_only_global(self):
        """Test summary with only global annotations."""
        kps = [
            Keypoint(image_id=0, image_name="img.tif", t=0, z=0, y=10.0, x=20.0, modality_idx=None),
            Keypoint(image_id=0, image_name="img.tif", t=1, z=0, y=15.0, x=25.0, modality_idx=None),
        ]
        
        summary = get_modality_summary(kps)
        
        assert summary == {None: 2}

    def test_summary_empty_list(self):
        """Test summary with empty list."""
        summary = get_modality_summary([])
        assert summary == {}

class TestMultiModalityIntegration:
    """Test integration of multi-modality features."""

    def test_workflow_filter_then_propagate(self, sample_keypoints):
        """Test workflow: filter modality 0, then propagate to modality 2."""
        # Step 1: Filter modality 0 (excluding global)
        modality_0 = filter_by_modality(sample_keypoints, modality_idx=0, show_all=False)
        assert len(modality_0) == 2
        
        # Step 2: Propagate to modality 2
        modality_2 = propagate_to_modality(modality_0, target_modality_idx=2)
        assert len(modality_2) == 2
        assert all(kp.modality_idx == 2 for kp in modality_2)

    def test_workflow_assign_then_filter(self):
        """Test workflow: create annotations, assign modality, then filter."""
        # Step 1: Create annotations
        kps = [
            Keypoint(image_id=0, image_name="img.tif", t=i, z=0, y=10.0*i, x=20.0*i, modality_idx=None)
            for i in range(5)
        ]
        
        # Step 2: Assign to modality 0
        assign_to_modality(kps, modality_idx=0)
        
        # Step 3: Filter by modality 0
        filtered = filter_by_modality(kps, modality_idx=0, show_all=False)
        assert len(filtered) == 5
        assert all(kp.modality_idx == 0 for kp in filtered)

    def test_summary_after_propagation(self, sample_keypoints):
        """Test summary updates correctly after propagation."""
        initial_summary = get_modality_summary(sample_keypoints)
        assert initial_summary == {0: 2, 1: 2, None: 2}
        
        # Propagate modality 0 to modality 2
        modality_0 = filter_by_modality(sample_keypoints, modality_idx=0, show_all=False)
        modality_2 = propagate_to_modality(modality_0, target_modality_idx=2)
        
        # Add propagated to original list
        all_annotations = sample_keypoints + modality_2
        
        new_summary = get_modality_summary(all_annotations)
        assert new_summary == {0: 2, 1: 2, 2: 2, None: 2}
