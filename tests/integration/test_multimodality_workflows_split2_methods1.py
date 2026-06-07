"""Method group 1 split from test_multimodality_workflows_split2.py."""

from __future__ import annotations

import json
import tempfile
from pathlib import Path

from phage_annotator.annotation.core import Keypoint
from phage_annotator.data.display_mapping import DisplayMapping
from phage_annotator.session.modality import ModalityManager


from tests.integration.test_multimodality_workflows_split1 import _make_keypoint, _visible_annotations

class _TestMultiModalityWorkflowsMethods1:
    """Methods split from TestMultiModalityWorkflows."""

    def test_create_three_modality_project_with_annotations(self):
        """Test creating project with 3 modalities and cross-modality annotations."""
        manager = ModalityManager()
        manager.add_modality(image_id=0, custom_name="DAPI")
        manager.add_modality(image_id=1, custom_name="GFP")
        manager.add_modality(image_id=2, custom_name="mCherry")

        assert manager.modality_count() == 3

        annotations = [
            _make_keypoint(
                x=100.0 + mod_idx * 50,
                y=200.0 + mod_idx * 50,
                z=5,
                modality_idx=mod_idx,
                image_id=mod_idx,
                image_name=f"test_image_{mod_idx}.tif",
            )
            for mod_idx in range(3)
        ]

        assert len(annotations) == 3
        assert [ann.modality_idx for ann in annotations] == [0, 1, 2]

    def test_annotation_filtering_by_modality(self):
        """Test that annotations are correctly filtered when switching modalities."""
        manager = ModalityManager()
        manager.add_modality(image_id=0, custom_name="DAPI")
        manager.add_modality(image_id=1, custom_name="GFP")

        annotations = [
            _make_keypoint(x=100, y=100, modality_idx=0, image_id=0, image_name="img0.tif"),
            _make_keypoint(x=150, y=150, modality_idx=0, image_id=0, image_name="img0.tif"),
            _make_keypoint(x=200, y=200, modality_idx=1, image_id=1, image_name="img1.tif"),
            _make_keypoint(x=250, y=250, modality_idx=1, image_id=1, image_name="img1.tif"),
        ]

        filtered_dapi = _visible_annotations(annotations, active_modality_idx=0)
        assert len(filtered_dapi) == 2
        assert all(ann.modality_idx == 0 for ann in filtered_dapi)

        filtered_gfp = _visible_annotations(annotations, active_modality_idx=1)
        assert len(filtered_gfp) == 2
        assert all(ann.modality_idx == 1 for ann in filtered_gfp)

    def test_legacy_annotations_visible_on_all_modalities(self):
        """Test that untagged (legacy) annotations appear on all modalities."""
        manager = ModalityManager()
        manager.add_modality(image_id=0, custom_name="DAPI")
        manager.add_modality(image_id=1, custom_name="GFP")

        annotations = [
            _make_keypoint(x=100, y=100, modality_idx=0, image_id=0, image_name="img0.tif"),
            _make_keypoint(
                x=150,
                y=150,
                modality_idx=None,
                image_id=0,
                image_name="img0.tif",
            ),
        ]

        assert len(_visible_annotations(annotations, active_modality_idx=0)) == 2

        filtered_gfp = _visible_annotations(annotations, active_modality_idx=1)
        assert len(filtered_gfp) == 1
        assert filtered_gfp[0].modality_idx is None

    def test_rename_modality_workflow(self):
        """Test renaming modalities and verifying it doesn't break references."""
        manager = ModalityManager()
        manager.add_modality(image_id=0, custom_name="CH1")
        manager.add_modality(image_id=1, custom_name="CH2")

        assert manager.modalities[0].display_name == "CH1"
        assert manager.modalities[1].display_name == "CH2"

        manager.rename_modality(0, "DAPI-405nm")
        assert manager.modalities[0].display_name == "DAPI-405nm"

        annotations = [
            _make_keypoint(
                x=100,
                y=100,
                modality_idx=0,
                image_id=0,
                image_name="img0.tif",
            )
        ]
        assert annotations[0].modality_idx == 0
        assert manager.modalities[0].display_name == "DAPI-405nm"

    def test_per_modality_contrast_settings(self):
        """Test per-modality contrast settings in DisplayMapping."""
        display = DisplayMapping(0.0, 4095.0)

        expected = {
            0: (0.0, 4095.0),
            1: (100.0, 3000.0),
            2: (200.0, 2500.0),
        }
        for image_id, (vmin, vmax) in expected.items():
            display.mapping_for(image_id, "frame").set_window(vmin, vmax)

        for image_id, (vmin, vmax) in expected.items():
            mapping = display.mapping_for(image_id, "frame")
            assert mapping.min_val == vmin
            assert mapping.max_val == vmax

    def test_contrast_sync_to_multiple_modalities(self):
        """Test sync target discovery and update application across modalities."""
        display = DisplayMapping(0.0, 4095.0)

        source = display.mapping_for(0, "frame")
        source.set_window(500.0, 3500.0)

        for target_id in (1, 2):
            target = display.mapping_for(target_id, "frame")
            target.set_sync_rules(sync_vmin=True, sync_vmax=True, sync_contrast=False)

        targets = display.propagate_sync_updates(source_image_id=0, panel="frame")
        assert (1, "frame") in targets
        assert (2, "frame") in targets

        for image_id, panel in targets:
            display.mapping_for(image_id, panel).set_window(source.min_val, source.max_val)

        assert display.mapping_for(1, "frame").min_val == 500.0
        assert display.mapping_for(1, "frame").max_val == 3500.0
        assert display.mapping_for(2, "frame").min_val == 500.0
        assert display.mapping_for(2, "frame").max_val == 3500.0

    def test_save_and_load_multimodality_project(self):
        """Test saving and loading a multi-modality project payload."""
        with tempfile.TemporaryDirectory() as tmpdir:
            project_path = Path(tmpdir) / "test_multimodal.phageproj"

            manager = ModalityManager()
            manager.add_modality(image_id=0, custom_name="DAPI")
            manager.add_modality(image_id=1, custom_name="GFP")
            manager.rename_modality(1, "GFP-488nm")

            annotations = [
                _make_keypoint(
                    x=100,
                    y=100,
                    modality_idx=0,
                    image_id=0,
                    image_name="img0.tif",
                ),
                _make_keypoint(
                    x=200,
                    y=200,
                    modality_idx=1,
                    image_id=1,
                    image_name="img1.tif",
                ),
            ]

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

            with open(project_path, "w", encoding="utf-8") as handle:
                json.dump(project_data, handle)

            with open(project_path, "r", encoding="utf-8") as handle:
                loaded_data = json.load(handle)

            assert loaded_data["schema_version"] == 2
            assert "modality_manager" in loaded_data
            assert len(loaded_data["modality_manager"]["modalities"]) == 2
            assert (
                loaded_data["modality_manager"]["modalities"][1]["display_name"]
                == "GFP-488nm"
            )
            assert len(loaded_data["annotations"]) == 2

    def test_backward_compatibility_legacy_project(self):
        """Test that legacy (v1) projects still have a clear upgrade path."""
        legacy_project = {
            "tool": "PhageAnnotator",
            "schema_version": 1,
            "images": [],
            "annotations": [{"x": 100, "y": 200, "z": 0, "t": 0}],
        }

        assert "modality_manager" not in legacy_project

        manager = ModalityManager()
        manager.add_modality(image_id=0, custom_name="Default")
        assert manager.modality_count() == 1

    def test_propagate_annotations_between_modalities(self):
        """Test copying annotations from one modality to another."""
        annotations = [
            _make_keypoint(x=100, y=100, modality_idx=0, image_id=0, image_name="img0.tif"),
            _make_keypoint(x=150, y=150, modality_idx=0, image_id=0, image_name="img0.tif"),
        ]

        propagated = []
        for ann in annotations:
            if ann.modality_idx == 0:
                propagated.append(
                    _make_keypoint(
                        x=ann.x,
                        y=ann.y,
                        z=ann.z,
                        t=ann.t,
                        label=ann.label,
                        modality_idx=1,
                        image_id=ann.image_id,
                        image_name=ann.image_name,
                    )
                )

        assert len(propagated) == 2
        assert all(ann.modality_idx == 1 for ann in propagated)
        assert propagated[0].x == annotations[0].x
        assert propagated[0].y == annotations[0].y
