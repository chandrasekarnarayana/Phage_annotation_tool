"""Regression tests for session annotation import/export flows."""

from __future__ import annotations

import json
from pathlib import Path
from types import SimpleNamespace

from phage_annotator.annotation.core import Keypoint
from phage_annotator.session.annotation_io import SessionAnnotationIOMixin


class _Harness(SessionAnnotationIOMixin):
    def __init__(self) -> None:
        """Initialize the object and prepare its runtime state."""
        self.session_state = SimpleNamespace(
            images=[
                SimpleNamespace(id=0, name="img_a.tif"),
                SimpleNamespace(id=1, name="img_b.tif"),
            ],
            annotation_imports={},
        )
        self._settings = None


class _DummySettings:
    def __init__(self, um_per_px: float) -> None:
        """Initialize the object and prepare its runtime state."""
        self._um_per_px = um_per_px

    def value(self, key: str, default=None, type=None):  # noqa: A002 - Qt-style signature
        """Run the value workflow."""
        if key == "defaultPixelSizeUmPerPx":
            return type(self._um_per_px) if callable(type) else self._um_per_px
        return default


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


def test_parse_thunderstorm_nm_uses_settings_default_pixel_size(tmp_path: Path) -> None:
    """ThunderSTORM nm coordinates should convert to px via default settings scale."""
    h = _Harness()
    h._settings = _DummySettings(um_per_px=0.069)  # 69 nm/px
    thunder = tmp_path / "thunder_nm.csv"
    thunder.write_text("frame,x [nm],y [nm]\n1,690,1380\n", encoding="utf-8")

    points, imports = h._parse_annotations_from_paths(
        [thunder],
        image_id=0,
        pixel_size_nm=None,
    )

    assert len(points) == 1
    assert points[0].x == 10.0
    assert points[0].y == 20.0
    assert imports[0][1]["format"] == "thunderstorm"
    assert imports[0][1]["pixel_size_nm"] == 69.0


def test_parse_thunderstorm_px_does_not_apply_nm_conversion(tmp_path: Path) -> None:
    """ThunderSTORM px coordinates should remain unchanged."""
    h = _Harness()
    h._settings = _DummySettings(um_per_px=0.069)  # Should not affect px-unit files
    thunder = tmp_path / "thunder_px.csv"
    thunder.write_text("frame,x [px],y [px]\n1,12.5,34.25\n", encoding="utf-8")

    points, imports = h._parse_annotations_from_paths(
        [thunder],
        image_id=0,
        pixel_size_nm=None,
    )

    assert len(points) == 1
    assert points[0].x == 12.5
    assert points[0].y == 34.25
    assert imports[0][1]["format"] == "thunderstorm"


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
