from __future__ import annotations

import json
from pathlib import Path
from types import SimpleNamespace

from phage_annotator.annotation.core import Keypoint
from phage_annotator.session.annotation_io import SessionAnnotationIOMixin


class _Harness(SessionAnnotationIOMixin):
    def __init__(self) -> None:
        self.session_state = SimpleNamespace(
            images=[
                SimpleNamespace(id=0, name="img_a.tif"),
                SimpleNamespace(id=1, name="img_b.tif"),
            ],
            annotation_imports={},
        )


def test_dedup_annotations_fallback_uses_xy_coordinates() -> None:
    """Regression: dedup fallback must use Keypoint.x/y, not legacy x_px/y_px."""
    h = _Harness()
    a = Keypoint(
        image_id=0,
        image_name="img_a.tif",
        t=0,
        z=0,
        y=10.0,
        x=20.0,
        label="phage",
        annotation_id="",
        meta={"import_file": "sample.csv"},
    )
    b = Keypoint(
        image_id=0,
        image_name="img_a.tif",
        t=0,
        z=0,
        y=10.01,
        x=20.01,
        label="phage",
        annotation_id="",
        meta={"import_file": "sample.csv"},
    )
    out = h._dedup_annotations([a, b], eps=0.25)
    assert len(out) == 1


def test_parse_annotations_mixed_legacy_and_thunderstorm(tmp_path: Path) -> None:
    """Mixed import parse path should preserve source tags and normalize image mapping."""
    h = _Harness()
    legacy = tmp_path / "legacy.csv"
    legacy.write_text("x,y\n10,20\n", encoding="utf-8")
    thunder = tmp_path / "thunder.csv"
    thunder.write_text("frame,x [px],y [px]\n1,30,40\n", encoding="utf-8")

    points, imports = h._parse_annotations_from_paths(
        [legacy, thunder],
        image_id=0,
        pixel_size_nm=100.0,
    )
    assert len(points) == 2
    sources = {p.source for p in points}
    assert "legacy_csv" in sources
    assert "thunderstorm_csv" in sources
    assert all(p.image_id == 0 for p in points)
    assert all(p.image_name == "img_a.tif" for p in points)
    assert len(imports) == 2


def test_parse_annotations_force_image_id_and_image_key_normalization(tmp_path: Path) -> None:
    """force_image_id should remap all points and normalize empty image_key."""
    h = _Harness()
    payload = {
        "unknown_image.tif": [
            {"t": 1, "z": 2, "x": 11.0, "y": 22.0, "label": "phage", "image_key": ""}
        ]
    }
    json_path = tmp_path / "points.json"
    json_path.write_text(json.dumps(payload), encoding="utf-8")

    points, imports = h._parse_annotations_from_paths(
        [json_path],
        image_id=0,
        pixel_size_nm=None,
        force_image_id=1,
    )
    assert len(points) == 1
    kp = points[0]
    assert kp.image_id == 1
    assert kp.image_name == "img_b.tif"
    assert kp.image_key == "img_b.tif"
    assert kp.meta.get("import_file", "").endswith("points.json")
    assert len(imports) == 1
    assert imports[0][0] == 1
    assert imports[0][1]["format"] == "json"


def test_latest_annotation_meta_returns_last_non_empty_meta() -> None:
    """latest_annotation_meta should return latest import metadata dict."""
    h = _Harness()
    h._record_annotation_imports(
        [
            (0, {"format": "legacy", "meta": {"pixel_size_nm": 100.0}}),
            (0, {"format": "thunderstorm", "meta": {"channel": "A"}}),
        ]
    )
    latest = h.latest_annotation_meta(0)
    assert latest == {"channel": "A"}
