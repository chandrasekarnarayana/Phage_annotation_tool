"""Method group 2 split from test_multimodality_workflows_split2.py."""

from __future__ import annotations

import json
import tempfile
from pathlib import Path

from phage_annotator.annotation.core import Keypoint
from phage_annotator.data.display_mapping import DisplayMapping
from phage_annotator.session.modality import ModalityManager


from tests.integration.test_multimodality_workflows_split1 import _make_keypoint, _visible_annotations

class _TestMultiModalityWorkflowsMethods2:
    """Methods split from TestMultiModalityWorkflows."""

    def test_remove_modality_cleanup(self):
        """Test that removing a modality allows annotation cleanup by index."""
        manager = ModalityManager()
        manager.add_modality(image_id=0, custom_name="DAPI")
        manager.add_modality(image_id=1, custom_name="GFP")

        annotations = [
            _make_keypoint(x=100, y=100, modality_idx=0, image_id=0, image_name="img0.tif"),
            _make_keypoint(x=150, y=150, modality_idx=1, image_id=1, image_name="img1.tif"),
            _make_keypoint(x=200, y=200, modality_idx=1, image_id=1, image_name="img1.tif"),
        ]

        manager.remove_modality(1)
        remaining_ids = {mod.idx for mod in manager.get_all_modalities()}

        cleaned = [
            ann
            for ann in annotations
            if ann.modality_idx is None or ann.modality_idx in remaining_ids
        ]

        assert len(cleaned) == 1
        assert cleaned[0].modality_idx == 0

    def test_zoom_pan_linking_across_modalities(self):
        """Test linking zoom/pan across modalities."""
        manager = ModalityManager()
        manager.add_modality(image_id=0, custom_name="DAPI")
        manager.add_modality(image_id=1, custom_name="GFP")
        manager.add_modality(image_id=2, custom_name="mCherry")

        manager.set_zoom_pan_link(0, 1, True)
        manager.set_zoom_pan_link(1, 2, True)

        assert manager.are_zoom_pan_linked(0, 1) is True
        assert manager.are_zoom_pan_linked(1, 2) is True
        assert manager.are_zoom_pan_linked(0, 2) is False

    def test_analysis_on_modality_subset(self):
        """Test running analysis on specific modality subset."""
        manager = ModalityManager()
        manager.add_modality(image_id=0, custom_name="DAPI")
        manager.add_modality(image_id=1, custom_name="GFP")
        manager.add_modality(image_id=2, custom_name="mCherry")

        target_modalities = [0, 1]
        results = {}
        for mod_idx in target_modalities:
            mod_spec = manager.modalities[mod_idx]
            results[mod_spec.display_name] = {
                "modality_idx": mod_idx,
                "particle_count": 100 + mod_idx * 20,
            }

        assert len(results) == 2
        assert "DAPI" in results
        assert "GFP" in results
        assert "mCherry" not in results

    def test_five_modality_complex_scenario(self):
        """Test complex scenario with 5 modalities, annotations, and settings."""
        manager = ModalityManager()
        modality_names = ["Ch405", "Ch488", "Ch561", "Ch633", "Ch730"]
        for image_id, name in enumerate(modality_names):
            manager.add_modality(image_id=image_id, custom_name=name)

        assert manager.modality_count() == 5

        annotations = []
        for mod_idx in range(5):
            for j in range(10):
                annotations.append(
                    _make_keypoint(
                        x=100.0 + j * 10,
                        y=200.0 + j * 10,
                        z=5 + j,
                        modality_idx=mod_idx,
                        image_id=mod_idx,
                        image_name=f"img{mod_idx}.tif",
                    )
                )

        assert len(annotations) == 50

        display = DisplayMapping(0.0, 4095.0)
        for image_id in range(5):
            vmin = float(image_id * 500)
            vmax = float(4095 - image_id * 300)
            display.mapping_for(image_id, "frame").set_window(vmin, vmax)

        for image_id in range(5):
            mapping = display.mapping_for(image_id, "frame")
            assert mapping.min_val == float(image_id * 500)
            assert mapping.max_val == float(4095 - image_id * 300)

        for i in range(4):
            manager.set_zoom_pan_link(i, i + 1, True)

        for i in range(4):
            assert manager.are_zoom_pan_linked(i, i + 1) is True
