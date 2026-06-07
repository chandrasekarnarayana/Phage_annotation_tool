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


class _Emitter:
    def __init__(self) -> None:
        """Initialize the object and prepare its runtime state."""
        self.count = 0

    def emit(self) -> None:
        """Emit emit for the current workflow."""
        self.count += 1

class _SettingsStub:
    def __init__(self) -> None:
        """Initialize the object and prepare its runtime state."""
        self.values: dict[str, Any] = {}

    def setValue(self, key: str, value: Any) -> None:
        """Run the setValue workflow."""
        self.values[str(key)] = value

class _Harness(SessionProjectMixin):
    def __init__(self) -> None:
        """Initialize the object and prepare its runtime state."""
        self.display_mapping = DisplayMapping(0.0, 1.0)
        self._settings = _SettingsStub()
        self._undo_stack: list[dict[str, Any]] = []
        self._redo_stack: list[dict[str, Any]] = []
        self._colormaps = ["gray"]
        self.rois_by_image: dict[int, list[Any]] = {}
        self.state_changed = _Emitter()
        self.annotations_changed = _Emitter()
        self.display_changed = _Emitter()
        self.view_state = ViewState()
        self.session_state = SimpleNamespace(
            images=[],
            annotations={},
            annotation_index={},
            annotations_loaded={},
            suggestions={},
            suggestion_history={},
            image_states={},
            threshold_configs_by_image={},
            particles_configs_by_image={},
            annotation_imports={},
            project_path=None,
            project_save_time=None,
            active_primary_id=0,
            active_support_id=0,
            smlm_runs=[],
            threshold_settings={},
            current_user="local_user",
            audit_log=[],
            suggestion_metrics={"generated": 0.0, "accepted": 0.0, "rejected": 0.0, "mean_correction_distance": 0.0},
            suggestion_strategy="current_view",
            suggestion_score_threshold=0.0,
            suggestion_auto_retrain_enabled=True,
            suggestion_auto_retrain_min_labels=25,
            annotation_space="stack",
            generation_space="stack",
            assist_min_total_labels=30,
            assist_min_positive_labels=15,
            assist_min_negative_labels=15,
            assist_min_labels_per_context=10,
            evidence_layer_config={},
            evidence_layer_presets={},
            disable_bulk_accept_when_stale=True,
            smlm_runbook_enabled=False,
            smlm_runbook_locked_profiles={},
            smlm_runbook_provenance=[],
            suggestion_ranker_state={},
            suggestion_training_samples=[],
            suggestion_training_pending=0,
            suggestion_context_stats={},
            modality_manager=None,
            channel_display_settings=None,
            density_config=None,
            density_infer_options=None,
            density_model_path=None,
            density_device="auto",
            density_target_panel="frame",
        )
        self._lut_set = None
        self._dirty = False

    def _build_image_state(self, img: Any) -> Any:
        """Build image state for the current workflow."""
        return SimpleNamespace(image_id=int(img.id), path=Path(img.path))

    def set_lut(self, value: int) -> None:
        """Set lut for the current workflow."""
        self._lut_set = int(value)

    def set_dirty(self, dirty: bool) -> None:
        """Set dirty for the current workflow."""
        self._dirty = bool(dirty)

def _mock_read_metadata(path: Path) -> Any:
    """Handle the mock read metadata helper flow."""
    return SimpleNamespace(path=path, name=path.name, id=-1, interpret_3d_as="auto")

def test_project_load_partial_missing_images_warns_and_succeeds(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Verify project load partial missing images warns and succeeds for the current workflow."""
    present = tmp_path / "present.tif"
    present.write_bytes(b"fake")
    missing = tmp_path / "missing.tif"
    project_path = tmp_path / "session.phageproj"
    project_path.write_text("{}", encoding="utf-8")

    def _fake_loader(_path: Path):
        """Handle the fake loader helper flow."""
        return (
            [
                {"path": str(present), "display_mapping": {}},
                {"path": str(missing), "display_mapping": {}},
            ],
            {"last_fov_index": 0, "last_support_index": 1},
            {},
            {},
            {},
            {},
            {},
            None,
            None,
        )

    warnings: list[tuple[str, str]] = []
    monkeypatch.setattr(project_module, "load_project", _fake_loader)
    monkeypatch.setattr(
        QtWidgets.QMessageBox,
        "warning",
        staticmethod(lambda _parent, title, text: warnings.append((str(title), str(text)))),
    )
    monkeypatch.setattr(QtWidgets.QMessageBox, "critical", staticmethod(lambda *_args, **_kwargs: None))

    harness = _Harness()
    ok = harness.load_project(None, project_path, _mock_read_metadata)

    assert ok is True
    assert len(harness.session_state.images) == 1
    assert harness.session_state.images[0].path == present
    assert warnings, "Expected missing-image warning during partial project load."
    report = dict(getattr(harness.session_state, "project_relink_report", {}) or {})
    assert report.get("partial_load") is True
    assert report.get("loaded_count") == 1
    assert report.get("skipped_count") == 1

def test_project_load_clamps_active_indices_after_partial_load(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Verify project load clamps active indices after partial load for the current workflow."""
    present = tmp_path / "present.tif"
    present.write_bytes(b"fake")
    missing = tmp_path / "missing.tif"
    project_path = tmp_path / "session.phageproj"
    project_path.write_text("{}", encoding="utf-8")

    def _fake_loader(_path: Path):
        """Handle the fake loader helper flow."""
        return (
            [
                {"path": str(missing), "display_mapping": {}},
                {"path": str(present), "display_mapping": {}},
            ],
            {"last_fov_index": 99, "last_support_index": 77},
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
    assert harness.session_state.active_primary_id == 0
    assert harness.session_state.active_support_id == 0

def test_project_load_fails_when_all_images_missing(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Verify project load fails when all images missing for the current workflow."""
    missing_a = tmp_path / "missing_a.tif"
    missing_b = tmp_path / "missing_b.tif"
    project_path = tmp_path / "session.phageproj"
    project_path.write_text("{}", encoding="utf-8")

    def _fake_loader(_path: Path):
        """Handle the fake loader helper flow."""
        return (
            [
                {"path": str(missing_a), "display_mapping": {}},
                {"path": str(missing_b), "display_mapping": {}},
            ],
            {"last_fov_index": 0, "last_support_index": 1},
            {},
            {},
            {},
            {},
            {},
            None,
            None,
        )

    critical_calls: list[tuple[str, str]] = []
    monkeypatch.setattr(project_module, "load_project", _fake_loader)
    monkeypatch.setattr(QtWidgets.QMessageBox, "warning", staticmethod(lambda *_args, **_kwargs: None))
    monkeypatch.setattr(
        QtWidgets.QMessageBox,
        "critical",
        staticmethod(lambda _parent, title, text: critical_calls.append((str(title), str(text)))),
    )

    harness = _Harness()
    ok = harness.load_project(None, project_path, _mock_read_metadata)

    assert ok is False
    assert critical_calls
    report = dict(getattr(harness.session_state, "project_relink_report", {}) or {})
    assert report.get("partial_load") is False
    assert report.get("loaded_count") == 0
