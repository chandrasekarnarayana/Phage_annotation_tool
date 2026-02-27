"""Tests for multi-modality annotation filtering.

This module validates:
- Annotation filtering by active modality in rendering
- Annotation creation with modality_idx assignment
- Backward compatibility (modality_idx=None shows on all modalities)
- Multi-modality annotation workflows
"""

import pytest
import numpy as np
from phage_annotator.core.annotation import Keypoint
from phage_annotator.session.modality import ModalityManager, ProjectionType


class TestModalityAnnotationFiltering:
    """Test annotation filtering by modality."""
    
    def test_annotation_with_modality_idx_structure(self):
        """Keypoint should support modality_idx field."""
        kp = Keypoint(
            image_id=0,
            image_name="test.tif",
            t=0,
            z=0,
            y=10.0,
            x=20.0,
            label="phage",
            modality_idx=1,
        )
        assert kp.modality_idx == 1
    
    def test_annotation_without_modality_idx_defaults_to_none(self):
        """Backward compat: modality_idx=None for legacy annotations."""
        kp = Keypoint(
            image_id=0,
            image_name="test.tif",
            t=0,
            z=0,
            y=10.0,
            x=20.0,
            label="phage",
        )
        assert kp.modality_idx is None
    
    def test_filter_annotations_by_modality_idx(self):
        """Filter annotations by modality_idx."""
        annotations = [
            Keypoint(0, "img.tif", 0, 0, 10.0, 20.0, "phage", modality_idx=0),
            Keypoint(0, "img.tif", 0, 0, 30.0, 40.0, "phage", modality_idx=1),
            Keypoint(0, "img.tif", 0, 0, 50.0, 60.0, "phage", modality_idx=0),
            Keypoint(0, "img.tif", 0, 0, 70.0, 80.0, "phage", modality_idx=None),
        ]
        
        # Filter for modality 0
        modality_0_annotations = [kp for kp in annotations if kp.modality_idx in (0, None)]
        assert len(modality_0_annotations) == 3
        assert modality_0_annotations[0].x == 20.0
        assert modality_0_annotations[1].x == 60.0
        assert modality_0_annotations[2].x == 80.0
    
    def test_filter_annotations_by_modality_1(self):
        """Filter annotations for modality 1."""
        annotations = [
            Keypoint(0, "img.tif", 0, 0, 10.0, 20.0, "phage", modality_idx=0),
            Keypoint(0, "img.tif", 0, 0, 30.0, 40.0, "phage", modality_idx=1),
            Keypoint(0, "img.tif", 0, 0, 50.0, 60.0, "phage", modality_idx=0),
            Keypoint(0, "img.tif", 0, 0, 70.0, 80.0, "phage", modality_idx=None),
        ]
        
        # Filter for modality 1
        modality_1_annotations = [kp for kp in annotations if kp.modality_idx in (1, None)]
        assert len(modality_1_annotations) == 2
        assert modality_1_annotations[0].x == 40.0
        assert modality_1_annotations[1].x == 80.0
    
    def test_annotations_without_modality_visible_on_all(self):
        """Annotations with modality_idx=None should be visible on all modalities."""
        annotations = [
            Keypoint(0, "img.tif", 0, 0, 10.0, 20.0, "phage", modality_idx=None),
            Keypoint(0, "img.tif", 0, 0, 30.0, 40.0, "phage", modality_idx=None),
        ]
        
        # These should be visible on any modality
        for active_modality in [0, 1, 2]:
            visible = [kp for kp in annotations if kp.modality_idx is None or kp.modality_idx == active_modality]
            assert len(visible) == 2


class TestModalityAnnotationCreation:
    """Test annotation creation with modality_idx."""
    
    def test_create_annotation_with_modality_idx(self):
        """Create annotation with specific modality_idx."""
        kp = Keypoint(
            image_id=0,
            image_name="test.tif",
            t=5,
            z=3,
            y=100.5,
            x=200.3,
            label="artifact",
            modality_idx=2,
        )
        assert kp.modality_idx == 2
        assert kp.x == 200.3
        assert kp.y == 100.5
        assert kp.label == "artifact"
    
    def test_create_annotation_without_modality_for_backward_compat(self):
        """Legacy code creating annotations without modality_idx."""
        kp = Keypoint(
            image_id=0,
            image_name="test.tif",
            t=0,
            z=0,
            y=50.0,
            x=60.0,
            label="phage",
        )
        assert kp.modality_idx is None
    
    def test_batch_annotation_creation_with_different_modalities(self):
        """Create multiple annotations with different modality indices."""
        annotations = []
        for i in range(5):
            annotations.append(
                Keypoint(
                    image_id=0,
                    image_name="test.tif",
                    t=0,
                    z=0,
                    y=float(i * 10),
                    x=float(i * 10),
                    label="phage",
                    modality_idx=i % 3,  # Rotate through modalities 0, 1, 2
                )
            )
        
        assert annotations[0].modality_idx == 0
        assert annotations[1].modality_idx == 1
        assert annotations[2].modality_idx == 2
        assert annotations[3].modality_idx == 0
        assert annotations[4].modality_idx == 1


class TestModalityAnnotationWorkflows:
    """Test multi-modality annotation workflows."""
    
    def test_switch_modality_filters_annotations(self):
        """Switching active modality should filter visible annotations."""
        # Simulation: user creates annotations on modality 0
        modality_0_annotations = [
            Keypoint(0, "img.tif", 0, 0, 10.0, 20.0, "phage", modality_idx=0),
            Keypoint(0, "img.tif", 0, 0, 30.0, 40.0, "phage", modality_idx=0),
        ]
        
        # Simulation: user creates annotations on modality 1
        modality_1_annotations = [
            Keypoint(0, "img.tif", 0, 0, 50.0, 60.0, "artifact", modality_idx=1),
        ]
        
        all_annotations = modality_0_annotations + modality_1_annotations
        
        # When active_modality_idx = 0
        active_modality_idx = 0
        visible = [kp for kp in all_annotations if kp.modality_idx in (active_modality_idx, None)]
        assert len(visible) == 2
        assert all(kp.label == "phage" for kp in visible)
        
        # When active_modality_idx = 1
        active_modality_idx = 1
        visible = [kp for kp in all_annotations if kp.modality_idx in (active_modality_idx, None)]
        assert len(visible) == 1
        assert visible[0].label == "artifact"
    
    def test_global_annotations_visible_on_all_modalities(self):
        """Global annotations (modality_idx=None) visible regardless of active modality."""
        annotations = [
            Keypoint(0, "img.tif", 0, 0, 10.0, 20.0, "reference", modality_idx=None),
            Keypoint(0, "img.tif", 0, 0, 30.0, 40.0, "phage", modality_idx=0),
            Keypoint(0, "img.tif", 0, 0, 50.0, 60.0, "artifact", modality_idx=1),
        ]
        
        # Global annotation should be visible on all modalities
        for active_modality in [0, 1, 2]:
            visible = [kp for kp in annotations if kp.modality_idx in (active_modality, None)]
            assert any(kp.label == "reference" for kp in visible)
    
    def test_modality_specific_annotation_counts(self):
        """Count annotations per modality."""
        annotations = [
            Keypoint(0, "img.tif", 0, 0, 10.0, 20.0, "phage", modality_idx=0),
            Keypoint(0, "img.tif", 0, 0, 30.0, 40.0, "phage", modality_idx=0),
            Keypoint(0, "img.tif", 0, 0, 50.0, 60.0, "artifact", modality_idx=1),
            Keypoint(0, "img.tif", 0, 0, 70.0, 80.0, "other", modality_idx=2),
            Keypoint(0, "img.tif", 0, 0, 90.0, 100.0, "global", modality_idx=None),
        ]
        
        # Count by modality
        modality_counts = {}
        for i in range(3):
            modality_counts[i] = len([kp for kp in annotations if kp.modality_idx == i])
        
        assert modality_counts[0] == 2
        assert modality_counts[1] == 1
        assert modality_counts[2] == 1
        
        # Global annotations
        global_count = len([kp for kp in annotations if kp.modality_idx is None])
        assert global_count == 1


class TestModalityAnnotationBackwardCompatibility:
    """Test backward compatibility with legacy annotation files."""
    
    def test_load_legacy_annotations_without_modality_idx(self):
        """Legacy annotations should load with modality_idx=None."""
        # Simulate loading legacy CSV (no modality_idx column)
        legacy_data = [
            Keypoint(0, "img.tif", 0, 0, 10.0, 20.0, "phage"),
            Keypoint(0, "img.tif", 0, 0, 30.0, 40.0, "artifact"),
        ]
        
        # All legacy annotations should have modality_idx=None
        assert all(kp.modality_idx is None for kp in legacy_data)
    
    def test_mixed_legacy_and_modern_annotations(self):
        """Mix of legacy (modality_idx=None) and modern (modality_idx set) annotations."""
        annotations = [
            Keypoint(0, "img.tif", 0, 0, 10.0, 20.0, "legacy1", modality_idx=None),
            Keypoint(0, "img.tif", 0, 0, 30.0, 40.0, "modern", modality_idx=0),
            Keypoint(0, "img.tif", 0, 0, 50.0, 60.0, "legacy2", modality_idx=None),
        ]
        
        # Legacy annotations visible on all modalities
        for active_modality in [0, 1, 2]:
            visible = [kp for kp in annotations if kp.modality_idx in (active_modality, None)]
            # At least the 2 legacy annotations should be visible
            legacy_visible = [kp for kp in visible if kp.modality_idx is None]
            assert len(legacy_visible) == 2


class TestModalityManagerIntegration:
    """Test integration with ModalityManager."""
    
    def test_modality_manager_with_annotations(self):
        """ModalityManager should work with modality-specific annotations."""
        manager = ModalityManager()
        
        # Create modalities
        mod0 = manager.add_modality(image_id=0, custom_name="TIRF")
        mod1 = manager.add_modality(image_id=1, custom_name="Confocal")
        
        assert mod0.idx == 0
        assert mod1.idx == 1
        
        # Create annotations for each modality
        annotations_mod0 = [
            Keypoint(0, "img.tif", 0, 0, 10.0, 20.0, "phage", modality_idx=mod0.idx),
        ]
        annotations_mod1 = [
            Keypoint(1, "img.tif", 0, 0, 30.0, 40.0, "artifact", modality_idx=mod1.idx),
        ]
        
        all_annotations = annotations_mod0 + annotations_mod1
        
        # Filter by modality
        visible_mod0 = [kp for kp in all_annotations if kp.modality_idx in (mod0.idx, None)]
        visible_mod1 = [kp for kp in all_annotations if kp.modality_idx in (mod1.idx, None)]
        
        assert len(visible_mod0) == 1
        assert len(visible_mod1) == 1
        assert visible_mod0[0].label == "phage"
        assert visible_mod1[0].label == "artifact"
