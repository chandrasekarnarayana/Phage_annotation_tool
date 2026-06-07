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


from tests.unit.test_qc_validators_split1 import create_mock_keypoint

@pytest.mark.order(3)
class TestQCValidatorIntegration:
    """Integration tests for QC validation."""
    
    def test_real_world_scenario(self):
        """Test realistic mixed scenario."""
        image_shape = (2048, 2048)
        
        keypoints = [
            # Normal annotations
            create_mock_keypoint(100, 100, label="prot_a", annotation_id="ann_1"),
            create_mock_keypoint(200, 200, label="prot_b", annotation_id="ann_2"),
            # Duplicate pair
            create_mock_keypoint(500, 500, label="prot_a", annotation_id="ann_3"),
            create_mock_keypoint(501, 501, label="prot_a", annotation_id="ann_4"),
            # Out of bounds
            create_mock_keypoint(-5, 100, label="prot_c", annotation_id="ann_5"),
            # Missing label
            create_mock_keypoint(1000, 1000, label="", annotation_id="ann_6"),
            # Density cluster
            create_mock_keypoint(1500, 1500, label="prot_d", annotation_id="ann_7"),
            create_mock_keypoint(1502, 1502, label="prot_d", annotation_id="ann_8"),
            create_mock_keypoint(1501, 1503, label="prot_d", annotation_id="ann_9"),
            create_mock_keypoint(1503, 1501, label="prot_d", annotation_id="ann_10"),
        ]
        
        issues = QCValidator.validate(
            keypoints,
            image_id="img_real",
            image_shape=image_shape,
        )
        
        # Should detect multiple issues
        assert len(issues) >= 2
        
        # Check for expected issue types
        issue_dict = {}
        for issue in issues:
            if issue.issue_type not in issue_dict:
                issue_dict[issue.issue_type] = []
            issue_dict[issue.issue_type].append(issue)
        
        # Should have detected some issues
        assert len(issue_dict) > 0

@pytest.mark.order(2)
class TestImageArtifactValidator:
    """Test image/stack artifact detection heuristics."""

    def test_detects_uneven_illumination(self):
        """Verify detects uneven illumination for the current workflow."""
        h, w = 128, 128
        yy, xx = np.mgrid[:h, :w]
        r = np.sqrt((xx - (w / 2.0)) ** 2 + (yy - (h / 2.0)) ** 2)
        frame = (300.0 - (3.5 * r)).astype(np.float32)
        frame = np.clip(frame, 5.0, None)
        stack = np.stack([frame, frame, frame], axis=0)
        issues = ImageArtifactValidator.find_artifacts(stack, image_id="img_illum")
        assert any(i.issue_type == "uneven_illumination" for i in issues)

    def test_detects_photobleaching(self):
        """Verify detects photobleaching for the current workflow."""
        frames = []
        for k in range(8):
            level = 200.0 - (k * 20.0)
            frames.append(np.full((64, 64), level, dtype=np.float32))
        stack = np.stack(frames, axis=0)
        issues = ImageArtifactValidator.find_artifacts(stack, image_id="img_bleach")
        assert any(i.issue_type == "photobleaching" for i in issues)

@pytest.mark.order(2)
class TestPoissonConsistencyValidator:
    """Test Poisson/Fano stochasticity checks."""

    def test_detects_image_stochasticity_deviation(self):
        """Verify detects image stochasticity deviation for the current workflow."""
        rng = np.random.default_rng(0)
        base = rng.normal(20.0, 3.0, size=(4, 64, 64)).astype(np.float32)
        base[:, :8, :8] += 120.0
        issues = PoissonConsistencyValidator.find_image_signal_stochasticity(base, image_id="img_stoch")
        assert any(i.issue_type == "image_stochasticity" for i in issues)

    def test_detects_annotation_stochasticity_clustered(self):
        """Verify detects annotation stochasticity clustered for the current workflow."""
        annotations = [
            create_mock_keypoint(10 + (i % 4), 10 + (i // 4), annotation_id=f"ann_{i}")
            for i in range(24)
        ]
        issues = PoissonConsistencyValidator.find_annotation_stochasticity(
            annotations=annotations,
            image_id="img_ann",
            image_shape=(512, 512),
        )
        assert any(i.issue_type == "annotation_stochasticity" for i in issues)
