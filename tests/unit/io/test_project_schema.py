import json
from types import SimpleNamespace

from phage_annotator.io.projects.base import (
    SCHEMA_VERSION,
    migrate_project_payload,
    save_project,
)


def test_save_project_writes_schema_fields(tmp_path) -> None:
    img = SimpleNamespace(id=0, path=str(tmp_path / "img.tif"), interpret_3d_as="auto")
    proj = tmp_path / "session.phageproj"
    save_project(proj, [img], {0: []}, {"last_fov_index": 0})

    data = json.loads(proj.read_text())
    assert data["schema_version"] == SCHEMA_VERSION
    assert "axis_contract" in data
    assert "annotation_meta_schema" in data


def test_migrate_project_payload_adds_defaults() -> None:
    legacy = {"tool": "PhageAnnotator", "version": "0.9.0", "images": [], "settings": {}}
    upgraded = migrate_project_payload(legacy)
    assert upgraded["schema_version"] == SCHEMA_VERSION
    assert "axis_contract" in upgraded
    assert "annotation_meta_schema" in upgraded
