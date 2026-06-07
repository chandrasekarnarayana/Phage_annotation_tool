"""Unit tests for session annotation export metadata."""

from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace

from phage_annotator.core.annotation import Keypoint
from phage_annotator.annotation.core import save_keypoints_csv, save_keypoints_json
from phage_annotator.data.display_mapping import DisplayMapping
from phage_annotator.io.metadata.annotation import parse_csv_header_meta, parse_json_meta
from phage_annotator.session.project import SessionProjectMixin


class _Harness(SessionProjectMixin):
    def __init__(self, image_path: Path) -> None:
        """Initialize the object and prepare its runtime state."""
        self.view_state = SimpleNamespace(
            roi_spec=SimpleNamespace(shape="box", x=10.0, y=20.0, w=100.0, h=50.0),
            crop_rect=(0.0, 0.0, 256.0, 256.0),
            annotation_scope="current",
            t=2,
            z=5,
        )
        image = SimpleNamespace(
            id=0,
            name=image_path.name,
            path=str(image_path),
            shape=(4, 8, 256, 256),
            dtype="uint16",
            has_time=True,
            has_z=True,
            ome_axes="TZYX",
            interpret_3d_as="depth",
        )
        self.session_state = SimpleNamespace(
            active_primary_id=0,
            images=[image],
            annotations={
                0: [
                    Keypoint(
                        image_id=0,
                        image_name=image.name,
                        t=2,
                        z=5,
                        y=42.0,
                        x=84.0,
                        label="Point",
                    )
                ]
            },
            annotation_space="stack",
            dirty=True,
        )
        self.display_mapping = DisplayMapping(0.0, 1.0)
        frame_map = self.display_mapping.mapping_for(0, "frame")
        frame_map.min_val = 12.0
        frame_map.max_val = 345.0
        frame_map.gamma = 1.3
        frame_map.lut = 2
        frame_map.invert = True

    def set_dirty(self, dirty: bool) -> None:
        """Set dirty for the current workflow."""
        self.session_state.dirty = bool(dirty)


def test_save_csv_includes_rich_export_metadata(tmp_path: Path) -> None:
    """Verify save csv includes rich export metadata for the current workflow."""
    image_path = tmp_path / "dataset_a.tif"
    image_path.write_bytes(b"fake")
    out_csv = tmp_path / "dataset_a.annotations.csv"
    harness = _Harness(image_path)

    meta = harness.build_annotation_export_metadata(
        0,
        export_format="csv",
        export_path=out_csv,
    )
    save_keypoints_csv(harness.session_state.annotations[0], out_csv, meta=meta)
    meta = parse_csv_header_meta(out_csv)

    assert meta["linked_image"]["image_name"] == "dataset_a.tif"
    assert meta["linked_image"]["image_path"].endswith("dataset_a.tif")
    assert meta["annotation_context"]["target"] == "frame"
    assert meta["annotation_context"]["scope"] == "current"
    assert meta["capture"]["crop"] == [0.0, 0.0, 256.0, 256.0]
    assert meta["capture"]["roi"]["shape"] == "box"
    assert "exported_at" in meta
    assert meta["annotation_count"] == 1


def test_save_json_includes_rich_export_metadata(tmp_path: Path) -> None:
    """Verify save json includes rich export metadata for the current workflow."""
    image_path = tmp_path / "dataset_b.tif"
    image_path.write_bytes(b"fake")
    out_json = tmp_path / "dataset_b.annotations.json"
    harness = _Harness(image_path)

    meta = harness.build_annotation_export_metadata(
        0,
        export_format="json",
        export_path=out_json,
    )
    save_keypoints_json(harness.session_state.annotations[0], out_json, meta=meta)
    meta = parse_json_meta(out_json)

    assert meta["linked_image"]["image_name"] == "dataset_b.tif"
    assert meta["capture"]["display_frame"]["win"]["min"] == 12.0
    assert meta["capture"]["display_frame"]["win"]["max"] == 345.0
    assert meta["capture"]["display_by_panel"]["frame"]["gamma"] == 1.3
    assert meta["annotation_context"]["annotation_space"] == "stack"
