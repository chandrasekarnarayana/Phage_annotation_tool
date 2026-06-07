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


def _make_keypoint(index: int, modality_idx: int | None) -> Keypoint:
    """Create a benchmark keypoint using the current annotation schema."""
    image_id = 0 if modality_idx is None else int(modality_idx)
    return Keypoint(
        image_id=image_id,
        image_name=f"img{image_id}.tif",
        t=0,
        z=index % 50,
        y=200.0 + (index % 1000),
        x=100.0 + (index % 1000),
        label="test",
        modality_idx=modality_idx,
    )

def _init_display_with_sync(num_modalities: int) -> DisplayMapping:
    """Create a display mapping with frame mappings and sync enabled on targets."""
    display = DisplayMapping(0.0, 4095.0)
    for image_id in range(num_modalities):
        frame_mapping = display.mapping_for(image_id, "frame")
        frame_mapping.set_window(0.0, 4095.0)
        if image_id != 0:
            frame_mapping.set_sync_rules(sync_vmin=True, sync_vmax=True)
    return display

class TestAnnotationFilteringPerformance:
    """Benchmark annotation filtering operations."""

    @pytest.mark.benchmark
    def test_filter_1000_annotations_by_modality(self, benchmark):
        """Benchmark filtering 1000 annotations by modality."""
        manager = ModalityManager()
        manager.add_modality(image_id=0, custom_name="DAPI")
        manager.add_modality(image_id=1, custom_name="GFP")

        annotations = [_make_keypoint(i, i % 2) for i in range(1000)]
        active_idx = 0

        def filter_annotations():
            """Run the filter annotations workflow."""
            return [
                ann
                for ann in annotations
                if ann.modality_idx is None or ann.modality_idx == active_idx
            ]

        result = benchmark(filter_annotations)
        assert len(result) == 500

    @pytest.mark.benchmark
    def test_filter_10000_annotations_by_modality(self, benchmark):
        """Benchmark filtering 10000 annotations by modality."""
        manager = ModalityManager()
        for i in range(10):
            manager.add_modality(image_id=i, custom_name=f"Ch{i}")

        annotations = [_make_keypoint(i, i % 10) for i in range(10000)]
        active_idx = 5

        def filter_annotations():
            """Run the filter annotations workflow."""
            return [
                ann
                for ann in annotations
                if ann.modality_idx is None or ann.modality_idx == active_idx
            ]

        result = benchmark(filter_annotations)
        assert len(result) == 1000

    @pytest.mark.benchmark
    def test_filter_with_legacy_annotations(self, benchmark):
        """Benchmark filtering with mix of legacy and modality-tagged annotations."""
        manager = ModalityManager()
        manager.add_modality(image_id=0, custom_name="DAPI")
        manager.add_modality(image_id=1, custom_name="GFP")

        annotations = [
            _make_keypoint(i, None if i % 5 == 0 else i % 2)
            for i in range(1000)
        ]
        active_idx = 0

        def filter_annotations():
            """Run the filter annotations workflow."""
            return [
                ann
                for ann in annotations
                if ann.modality_idx is None or ann.modality_idx == active_idx
            ]

        result = benchmark(filter_annotations)
        assert len(result) == 600

class TestContrastSyncPerformance:
    """Benchmark contrast synchronization operations."""

    @pytest.mark.benchmark
    def test_sync_contrast_to_3_modalities(self, benchmark):
        """Benchmark syncing contrast to 3 modalities."""
        display = _init_display_with_sync(3)

        def sync_contrast():
            """Synchronize contrast for the current workflow."""
            source = display.mapping_for(0, "frame")
            source.set_window(500.0, 3500.0)

            targets = display.propagate_sync_updates(source_image_id=0, panel="frame")
            for image_id, panel in targets:
                display.mapping_for(image_id, panel).set_window(source.min_val, source.max_val)

            target_mapping = display.mapping_for(1, "frame")
            return (target_mapping.min_val, target_mapping.max_val)

        result = benchmark(sync_contrast)
        assert result == (500.0, 3500.0)

    @pytest.mark.benchmark
    def test_sync_contrast_to_10_modalities(self, benchmark):
        """Benchmark syncing contrast to 10 modalities."""
        display = _init_display_with_sync(10)

        def sync_contrast():
            """Synchronize contrast for the current workflow."""
            source = display.mapping_for(0, "frame")
            source.set_window(500.0, 3500.0)

            targets = display.propagate_sync_updates(source_image_id=0, panel="frame")
            for image_id, panel in targets:
                display.mapping_for(image_id, panel).set_window(source.min_val, source.max_val)

            return all(
                display.mapping_for(i, "frame").min_val == 500.0
                and display.mapping_for(i, "frame").max_val == 3500.0
                for i in range(1, 10)
            )

        result = benchmark(sync_contrast)
        assert result is True

    @pytest.mark.benchmark
    def test_sync_chain_propagation(self, benchmark):
        """Benchmark chained sync propagation (0->1->2->...->9)."""
        display = DisplayMapping(0.0, 4095.0)
        for i in range(10):
            display.mapping_for(i, "frame").set_window(float(i * 100), float(4095 - i * 100))

        def chain_sync():
            """Run the chain sync workflow."""
            for i in range(9):
                source = display.mapping_for(i, "frame")
                target = display.mapping_for(i + 1, "frame")
                target.set_window(source.min_val, source.max_val)
            final = display.mapping_for(9, "frame")
            return (final.min_val, final.max_val)

        result = benchmark(chain_sync)
        assert result == (0.0, 4095.0)

class TestProjectSaveLoadPerformance:
    """Benchmark project serialization performance."""

    @pytest.mark.benchmark
    def test_save_project_with_10k_annotations(self, benchmark):
        """Benchmark saving project with 10,000 annotations."""
        manager = ModalityManager()
        manager.add_modality(image_id=0, custom_name="DAPI")
        manager.add_modality(image_id=1, custom_name="GFP")

        annotations = [_make_keypoint(i, i % 2) for i in range(10000)]

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

        with tempfile.TemporaryDirectory() as tmpdir:
            project_path = Path(tmpdir) / "test.phageproj"

            def save():
                """Save save for the current workflow."""
                with open(project_path, "w", encoding="utf-8") as handle:
                    json.dump(project_data, handle)

            benchmark(save)
            assert project_path.exists()

    @pytest.mark.benchmark
    def test_load_project_with_10k_annotations(self, benchmark):
        """Benchmark loading project with 10,000 annotations."""
        manager = ModalityManager()
        manager.add_modality(image_id=0, custom_name="DAPI")
        manager.add_modality(image_id=1, custom_name="GFP")

        annotations = [
            {
                "image_id": i % 2,
                "image_name": f"img{i % 2}.tif",
                "t": 0,
                "z": i % 100,
                "y": 200.0 + i % 1000,
                "x": 100.0 + i % 1000,
                "label": "test",
                "modality_idx": i % 2,
            }
            for i in range(10000)
        ]

        project_data = {
            "tool": "PhageAnnotator",
            "schema_version": 2,
            "modality_manager": manager.to_dict(),
            "annotations": annotations,
        }

        with tempfile.TemporaryDirectory() as tmpdir:
            project_path = Path(tmpdir) / "test.phageproj"
            with open(project_path, "w", encoding="utf-8") as handle:
                json.dump(project_data, handle)

            def load():
                """Load load for the current workflow."""
                with open(project_path, "r", encoding="utf-8") as handle:
                    return json.load(handle)

            result = benchmark(load)
            assert result["schema_version"] == 2
            assert len(result["annotations"]) == 10000

class TestMultiModalityMemoryUsage:
    """Benchmark memory usage with multiple modalities."""

    @pytest.mark.benchmark
    def test_memory_with_incremental_modalities(self):
        """Measure memory growth as modalities are added."""
        import sys

        manager = ModalityManager()
        baseline_size = sys.getsizeof(manager)

        sizes = [baseline_size]
        for i in range(10):
            manager.add_modality(image_id=i, custom_name=f"Ch{i}")
            sizes.append(sys.getsizeof(manager))

        growth_per_modality = [sizes[i] - sizes[i - 1] for i in range(1, len(sizes))]
        avg_growth = sum(growth_per_modality) / len(growth_per_modality)

        assert avg_growth < 10000
