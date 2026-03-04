from __future__ import annotations

import json
from pathlib import Path

from phage_annotator.io.projects.base import load_project


def test_load_project_resolves_relative_annotation_path(tmp_path: Path) -> None:
    project_path = tmp_path / "session.phageproj"
    image_path = tmp_path / "sample_stack.tif"
    ann_path = tmp_path / "sample_stack.annotations.json"
    image_path.write_bytes(b"fake")
    ann_path.write_text('{"sample_stack.tif": []}', encoding="utf-8")
    payload = {
        "tool": "PhageAnnotator",
        "version": "0.9.0",
        "schema_version": 3,
        "images": [
            {
                "path": str(image_path),
                "annotations": str(tmp_path / "missing.annotations.json"),
                "annotations_relative": "sample_stack.annotations.json",
            }
        ],
        "settings": {},
    }
    project_path.write_text(json.dumps(payload), encoding="utf-8")

    images, _settings, ann_map, *_rest = load_project(project_path)
    assert images[0]["path"] == str(image_path)
    assert 0 in ann_map
    assert ann_map[0] == ann_path


def test_load_project_falls_back_to_sidecar_annotation(tmp_path: Path) -> None:
    project_path = tmp_path / "session.phageproj"
    image_path = tmp_path / "moved_stack.tif"
    sidecar = tmp_path / "moved_stack.annotations.json"
    image_path.write_bytes(b"fake")
    sidecar.write_text('{"moved_stack.tif": []}', encoding="utf-8")
    payload = {
        "tool": "PhageAnnotator",
        "version": "0.9.0",
        "schema_version": 3,
        "images": [{"path": str(image_path), "annotations": str(tmp_path / "now_missing.json")}],
        "settings": {},
    }
    project_path.write_text(json.dumps(payload), encoding="utf-8")

    _images, _settings, ann_map, *_rest = load_project(project_path)
    assert ann_map[0] == sidecar
