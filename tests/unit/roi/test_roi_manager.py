"""Unit tests for ROI manager logic and ROI package exports."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import numpy as np

from phage_annotator.roi.auto import propose_roi
from phage_annotator.roi.manager import Roi, RoiManager, load_rois_json, save_rois_json


@dataclass
class _RoiSummary:
    count: int
    names: list[str]


def _summary(manager: RoiManager, image_id: int) -> _RoiSummary:
    rois = manager.list_rois(image_id)
    return _RoiSummary(count=len(rois), names=[roi.name for roi in rois])


def test_roi_manager_copy_and_template_workflow() -> None:
    """ROI copy/template operations should preserve geometry and metadata."""
    manager = RoiManager()
    source_roi = Roi(
        roi_id=1,
        name="cell",
        roi_type="box",
        points=[(10.0, 20.0), (40.0, 60.0)],
    )
    manager.add_roi(image_id=0, roi=source_roi)

    copied = manager.copy_roi_to_images(0, roi_id=1, target_image_ids=[0, 1, 2])
    assert copied == 2
    assert _summary(manager, 1).count == 1
    assert _summary(manager, 2).count == 1

    manager.save_roi_template("default-box", source_roi)
    applied = manager.apply_template_to_image("default-box", image_id=3)
    assert applied is True
    assert _summary(manager, 3).names == ["default-box"]


def test_roi_manager_json_roundtrip(tmp_path: Path) -> None:
    """ROI JSON helpers should roundtrip IDs, points, and visibility."""
    rois = [
        Roi(roi_id=7, name="a", roi_type="box", points=[(1.0, 2.0), (3.0, 4.0)], visible=True),
        Roi(
            roi_id=8,
            name="b",
            roi_type="circle",
            points=[(5.0, 6.0), (7.0, 8.0)],
            visible=False,
        ),
    ]
    out = tmp_path / "rois.json"
    save_rois_json(out, rois)
    loaded = load_rois_json(out)
    assert [r.roi_id for r in loaded] == [7, 8]
    assert [r.name for r in loaded] == ["a", "b"]
    assert loaded[1].visible is False
    assert loaded[0].points == [(1.0, 2.0), (3.0, 4.0)]


def test_roi_auto_facade_exports_propose_roi() -> None:
    """The roi.auto facade should route to the auto ROI algorithm."""
    image = np.ones((128, 128), dtype=np.float32)
    spec, info = propose_roi(image, request_w=48, request_h=48)
    x, y, w, h = spec.rect
    assert isinstance(info, dict)
    assert "score" in info
    assert isinstance(info["score"], float)
    assert spec.shape in {"box", "circle"}
    assert w > 0 and h > 0
    assert 0.0 <= x <= 128.0
    assert 0.0 <= y <= 128.0
