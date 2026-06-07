"""Split definitions from test_multimodality_perf.py."""

from __future__ import annotations

import json
import tempfile
from pathlib import Path

import pytest

pytest.importorskip("pytest_benchmark")

from phage_annotator.annotation.core import Keypoint
from phage_annotator.data.display_mapping import DisplayMapping
from phage_annotator.session.modality import ModalityManager


from tests.performance.test_multimodality_perf_split1 import _make_keypoint, _init_display_with_sync

class TestAnnotationCreationPerformance:
    """Benchmark annotation creation and organization."""

    @pytest.mark.benchmark
    def test_create_and_organize_1000_annotations(self, benchmark):
        """Benchmark creating and organizing 1000 annotations."""

        def create_annotations():
            """Create annotations for the current workflow."""
            return [_make_keypoint(i, i % 5) for i in range(1000)]

        result = benchmark(create_annotations)
        assert len(result) == 1000
        assert all(isinstance(ann, Keypoint) for ann in result)

    @pytest.mark.benchmark
    def test_organize_annotations_by_modality(self, benchmark):
        """Benchmark organizing annotations by modality."""
        annotations = [_make_keypoint(i, i % 5) for i in range(1000)]

        def organize():
            """Run the organize workflow."""
            by_modality: dict[int | None, list[Keypoint]] = {}
            for ann in annotations:
                by_modality.setdefault(ann.modality_idx, []).append(ann)
            return by_modality

        result = benchmark(organize)
        assert all(len(anns) == 200 for anns in result.values())

@pytest.mark.benchmark
class TestComplexWorkflowPerformance:
    """Benchmark complete workflows."""

    @pytest.mark.benchmark
    def test_full_workflow_5_modalities_5k_annotations(self, benchmark):
        """Benchmark complete workflow: create, annotate, sync, save."""

        def full_workflow():
            """Run the full workflow workflow."""
            manager = ModalityManager()
            display = _init_display_with_sync(5)

            for i in range(5):
                manager.add_modality(image_id=i, custom_name=f"Ch{i}")

            annotations = [_make_keypoint(i, i % 5) for i in range(5000)]

            source = display.mapping_for(0, "frame")
            source.set_window(500.0, 3500.0)
            targets = display.propagate_sync_updates(source_image_id=0, panel="frame")
            for image_id, panel in targets:
                display.mapping_for(image_id, panel).set_window(source.min_val, source.max_val)

            project_data = {
                "tool": "PhageAnnotator",
                "schema_version": 2,
                "modality_manager": manager.to_dict(),
                "annotations": [
                    {
                        "image_id": ann.image_id,
                        "image_name": ann.image_name,
                        "t": ann.t,
                        "z": ann.z,
                        "y": ann.y,
                        "x": ann.x,
                        "label": ann.label,
                        "modality_idx": ann.modality_idx,
                    }
                    for ann in annotations
                ],
            }

            return len(project_data["annotations"])

        result = benchmark(full_workflow)
        assert result == 5000
