"""Split definitions from test_project_load_resilience.py."""

from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace
from typing import Any

import pytest
from matplotlib.backends.qt_compat import QtWidgets

from phage_annotator.core.session_state import ViewState
from phage_annotator.data.display_mapping import DisplayMapping
import phage_annotator.session.project as project_module
from phage_annotator.session.project import SessionProjectMixin


from tests.unit.session.test_project_load_resilience_split1 import _Harness, _mock_read_metadata

def test_project_load_prefers_workspace_snapshot_display_mapping_over_legacy_lut(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Workspace snapshot display mapping should win over legacy LUT fallback."""
    present = tmp_path / "present.tif"
    present.write_bytes(b"fake")
    project_path = tmp_path / "session.phageproj"
    project_path.write_text("{}", encoding="utf-8")

    def _fake_loader(_path: Path):
        """Handle the fake loader helper flow."""
        return (
            [
                {"path": str(present), "display_mapping": {}},
            ],
            {
                "last_fov_index": 0,
                "last_support_index": 0,
                "lut": 0,
                "workspace_snapshot": {
                    "session_workspace": {
                        "active_primary_id": 0,
                        "display_mapping_frame": {
                            "min": 5.0,
                            "max": 15.0,
                            "gamma": 1.3,
                            "lut": 2,
                            "invert": True,
                        },
                    }
                },
            },
            {},
            {},
            {},
            {},
            {},
            None,
            None,
        )

    monkeypatch.setattr(project_module, "load_project", _fake_loader)
    monkeypatch.setattr(QtWidgets.QMessageBox, "warning", staticmethod(lambda *_args, **_kwargs: None))
    monkeypatch.setattr(QtWidgets.QMessageBox, "critical", staticmethod(lambda *_args, **_kwargs: None))

    harness = _Harness()
    ok = harness.load_project(None, project_path, _mock_read_metadata)

    assert ok is True
    mapping = harness.display_mapping.mapping_for(0, "frame")
    assert mapping.min_val == 5.0
    assert mapping.max_val == 15.0
    assert mapping.gamma == 1.3
    assert mapping.lut == 2
    assert mapping.invert is True
    assert harness._lut_set is None
    assert "Load failed" in critical_calls[0][0]

def test_project_load_relinks_image_via_relative_path(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Verify project load relinks image via relative path for the current workflow."""
    project_path = tmp_path / "session.phageproj"
    project_path.write_text("{}", encoding="utf-8")
    moved_dir = tmp_path / "moved"
    moved_dir.mkdir(parents=True, exist_ok=True)
    relinked = moved_dir / "relocated.tif"
    relinked.write_bytes(b"fake")
    original = tmp_path / "old_location" / "relocated.tif"

    def _fake_loader(_path: Path):
        """Handle the fake loader helper flow."""
        return (
            [
                {
                    "path": str(original),
                    "path_relative": "moved/relocated.tif",
                    "image_name": "relocated.tif",
                    "display_mapping": {},
                }
            ],
            {"last_fov_index": 0, "last_support_index": 0},
            {},
            {},
            {},
            {},
            {},
            None,
            None,
        )

    monkeypatch.setattr(project_module, "load_project", _fake_loader)
    monkeypatch.setattr(QtWidgets.QMessageBox, "warning", staticmethod(lambda *_args, **_kwargs: None))
    monkeypatch.setattr(QtWidgets.QMessageBox, "critical", staticmethod(lambda *_args, **_kwargs: None))

    harness = _Harness()
    ok = harness.load_project(None, project_path, _mock_read_metadata)

    assert ok is True
    assert len(harness.session_state.images) == 1
    assert Path(harness.session_state.images[0].path) == relinked

def test_project_load_manual_relink_from_user_selected_folder(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Verify project load manual relink from user selected folder for the current workflow."""
    project_path = tmp_path / "session.phageproj"
    project_path.write_text("{}", encoding="utf-8")
    missing = tmp_path / "gone" / "manual_relink.tif"
    manual_dir = tmp_path / "manual_pick"
    manual_dir.mkdir(parents=True, exist_ok=True)
    recovered = manual_dir / "manual_relink.tif"
    recovered.write_bytes(b"fake")

    def _fake_loader(_path: Path):
        """Handle the fake loader helper flow."""
        return (
            [
                {
                    "path": str(missing),
                    "image_name": "manual_relink.tif",
                    "display_mapping": {},
                }
            ],
            {"last_fov_index": 0, "last_support_index": 0},
            {},
            {},
            {},
            {},
            {},
            None,
            None,
        )

    monkeypatch.setattr(project_module, "load_project", _fake_loader)
    monkeypatch.setattr(
        QtWidgets.QMessageBox,
        "question",
        staticmethod(lambda *_args, **_kwargs: QtWidgets.QMessageBox.StandardButton.Yes),
    )
    monkeypatch.setattr(
        QtWidgets.QFileDialog,
        "getExistingDirectory",
        staticmethod(lambda *_args, **_kwargs: str(manual_dir)),
    )
    monkeypatch.setattr(QtWidgets.QMessageBox, "warning", staticmethod(lambda *_args, **_kwargs: None))
    monkeypatch.setattr(QtWidgets.QMessageBox, "critical", staticmethod(lambda *_args, **_kwargs: None))

    harness = _Harness()
    ok = harness.load_project(None, project_path, _mock_read_metadata)

    assert ok is True
    assert len(harness.session_state.images) == 1
    assert Path(harness.session_state.images[0].path) == recovered

def test_project_load_manual_relink_per_file_selection(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Verify project load manual relink per file selection for the current workflow."""
    project_path = tmp_path / "session.phageproj"
    project_path.write_text("{}", encoding="utf-8")
    missing = tmp_path / "gone" / "manual_single_pick.tif"
    manual = tmp_path / "manual_single_pick.tif"
    manual.write_bytes(b"fake")

    def _fake_loader(_path: Path):
        """Handle the fake loader helper flow."""
        return (
            [
                {
                    "path": str(missing),
                    "image_name": "manual_single_pick.tif",
                    "display_mapping": {},
                }
            ],
            {"last_fov_index": 0, "last_support_index": 0},
            {},
            {},
            {},
            {},
            {},
            None,
            None,
        )

    monkeypatch.setattr(project_module, "load_project", _fake_loader)
    monkeypatch.setattr(
        QtWidgets.QMessageBox,
        "question",
        staticmethod(lambda *_args, **_kwargs: QtWidgets.QMessageBox.StandardButton.No),
    )
    monkeypatch.setattr(
        QtWidgets.QFileDialog,
        "getOpenFileName",
        staticmethod(lambda *_args, **_kwargs: (str(manual), "")),
    )
    monkeypatch.setattr(QtWidgets.QMessageBox, "warning", staticmethod(lambda *_args, **_kwargs: None))
    monkeypatch.setattr(QtWidgets.QMessageBox, "critical", staticmethod(lambda *_args, **_kwargs: None))

    harness = _Harness()
    ok = harness.load_project(None, project_path, _mock_read_metadata)

    assert ok is True
    assert len(harness.session_state.images) == 1
    assert Path(harness.session_state.images[0].path) == manual
