"""Focused unit coverage for manual sync-group selection behavior."""

from __future__ import annotations

from types import SimpleNamespace

from matplotlib.backends.qt_compat import QtWidgets

from phage_annotator.session.modality import ProjectionType
from phage_annotator.ui_qt.controls.display import DisplayControlsMixin


class _ModalityManagerStub:
    def __init__(self, modalities):
        """Initialize the object and prepare its runtime state."""
        self._modalities = {int(modality.idx): modality for modality in modalities}

    def get_modality(self, idx: int):
        """Return modality for the current workflow."""
        return self._modalities.get(int(idx))


class _SyncHarness(DisplayControlsMixin):
    _selected_sync_panels = DisplayControlsMixin._selected_sync_panels
    _selected_playback_modalities = DisplayControlsMixin._selected_playback_modalities
    _contrast_target_panels = DisplayControlsMixin._contrast_target_panels
    _sync_contract_summary = DisplayControlsMixin._sync_contract_summary
    _sync_panel_summary = DisplayControlsMixin._sync_panel_summary
    _sync_view_summary = DisplayControlsMixin._sync_view_summary
    _sync_follow_active_enabled = DisplayControlsMixin._sync_follow_active_enabled
    _sync_key_for_panel = DisplayControlsMixin._sync_key_for_panel
    _sync_mode_enabled_for_panel = DisplayControlsMixin._sync_mode_enabled_for_panel
    _set_sync_key_combo_data = DisplayControlsMixin._set_sync_key_combo_data
    _sync_key_active_group = DisplayControlsMixin._sync_key_active_group
    _propagate_sync_to_modalities = DisplayControlsMixin._propagate_sync_to_modalities
    _apply_view_sync_selection = DisplayControlsMixin._apply_view_sync_selection
    _apply_playback_sync_selection = DisplayControlsMixin._apply_playback_sync_selection

    def __init__(self, parent) -> None:
        """Initialize the object and prepare its runtime state."""
        self.sync_target_mode_combo = QtWidgets.QComboBox(parent)
        self.sync_target_mode_combo.addItem("Manual group", "manual")
        self.sync_target_mode_combo.addItem("Active canvas group", "active")
        self.sync_target_mode_combo.setCurrentIndex(0)
        self.sync_key_combo = QtWidgets.QComboBox(parent)
        self.sync_key_combo.addItem("Group 1", "1")
        self.sync_key_combo.addItem("Group 2", "2")
        self._panel_sync_index = {"frame": 0, "support": 1, "modality_2": 2}
        self._panel_sync_reverse = {0: "frame", 1: "support", 2: "modality_2"}
        self.annotate_target = "frame"
        self._last_display_shape = (100, 200)
        frame = SimpleNamespace(idx=0, image_id=0, projection_type=ProjectionType.RAW, display_name="Frame")
        support = SimpleNamespace(idx=1, image_id=1, projection_type=ProjectionType.RAW, display_name="Support")
        mean = SimpleNamespace(idx=2, image_id=0, projection_type=ProjectionType.MEAN, display_name="Mean")
        self._panel_modality_map = {"frame": frame, "support": support, "modality_2": mean}
        self.renderer = SimpleNamespace(
            axes={
                "frame": SimpleNamespace(get_xlim=lambda: (0.0, 100.0), get_ylim=lambda: (100.0, 0.0)),
                "support": SimpleNamespace(get_xlim=lambda: (10.0, 110.0), get_ylim=lambda: (120.0, 20.0)),
                "modality_2": SimpleNamespace(get_xlim=lambda: (20.0, 120.0), get_ylim=lambda: (130.0, 30.0)),
            }
        )
        self.controller = SimpleNamespace(
            session_state=SimpleNamespace(
                modality_manager=_ModalityManagerStub([frame, support, mean]),
            ),
            display_mapping=SimpleNamespace(
                propagate_sync_updates=lambda image_id, panel: [
                    (1, "support"),
                    (0, "frame"),
                    (0, "modality_2"),
                ]
            ),
        )
        self._lazy_sync_groups_state = lambda: {0: "1", 1: "2", 2: "2"}
        self._lazy_sync_modes_state = lambda: {
            0: {"contrast": True, "zoom": True, "playback": True},
            1: {"contrast": True, "zoom": False, "playback": True},
            2: {"contrast": False, "zoom": True, "playback": False},
        }
        self.modality_playback = SimpleNamespace(set_sync_group=lambda value: setattr(self, "_last_sync_group", value))
        self._last_sync_group = None
        self._view_sync_calls = []
        self.view_sync = SimpleNamespace(
            clear=lambda: self._view_sync_calls.append(("clear",)),
            register_modality=lambda idx: self._view_sync_calls.append(("register", int(idx))),
            create_link_group=lambda group: self._view_sync_calls.append(("group", tuple(sorted(int(v) for v in group)))),
            enable_zoom_sync=lambda value: self._view_sync_calls.append(("zoom", bool(value))),
            enable_pan_sync=lambda value: self._view_sync_calls.append(("pan", bool(value))),
        )
        self.images = [
            SimpleNamespace(id=0, array=SimpleNamespace(shape=(2, 10, 10))),
            SimpleNamespace(id=1, array=SimpleNamespace(shape=(2, 10, 10))),
        ]
        self._updated_windows = []

    def _image_obj_from_id(self, image_id: int):
        """Handle the image obj from id helper flow."""
        for image in self.images:
            if int(getattr(image, "id", -1)) == int(image_id):
                return image
        return None

    def _get_display_mapping(self, image_id, panel, _data):
        """Return display mapping for the current workflow."""
        mapping = SimpleNamespace(
            min_val=0.0,
            max_val=1.0,
            set_window=lambda min_val, max_val: self._updated_windows.append(
                (int(image_id), str(panel), float(min_val), float(max_val))
            ),
        )
        return mapping

    def _sync_modality_display_settings(self, _panel, _mapping) -> None:
        """Synchronize modality display settings for the current workflow."""
        return

    def _default_panel_key(self) -> str:
        """Handle the default panel key helper flow."""
        return "frame"


def test_manual_sync_group_selection_targets_expected_panels_and_modes(qtbot) -> None:
    """Manual group selection should drive panel, contrast, and playback targeting."""
    parent = QtWidgets.QWidget()
    qtbot.addWidget(parent)
    harness = _SyncHarness(parent)

    harness.sync_key_combo.setCurrentIndex(harness.sync_key_combo.findData("2"))

    assert harness._selected_sync_panels() == ["support", "modality_2"]
    assert harness._contrast_target_panels() == ["support"]
    assert harness._selected_playback_modalities() == {1}
    assert harness._sync_contract_summary() == "Sync contract: Group 2 | Contrast, Zoom/Pan, Playback"
    assert harness._sync_panel_summary() == "Sync panels: Support, Mean"
    assert harness._sync_view_summary() == "Sync view: support | Zoom 2.00x | Pan 10, 20"


def test_playback_sync_selection_does_not_fallback_to_all_when_group_has_no_raw_targets(qtbot) -> None:
    """Selected playback group with only non-raw panels should resolve to an empty sync group."""
    parent = QtWidgets.QWidget()
    qtbot.addWidget(parent)
    harness = _SyncHarness(parent)

    harness.sync_key_combo.setCurrentIndex(harness.sync_key_combo.findData("2"))
    harness._lazy_sync_modes_state = lambda: {
        0: {"contrast": True, "zoom": True, "playback": True},
        1: {"contrast": True, "zoom": False, "playback": False},
        2: {"contrast": False, "zoom": True, "playback": False},
    }

    harness._apply_playback_sync_selection()

    assert harness._last_sync_group == set()


def test_contrast_propagation_respects_selected_sync_group(qtbot) -> None:
    """Legacy contrast propagation should still respect the currently selected sync group."""
    parent = QtWidgets.QWidget()
    qtbot.addWidget(parent)
    harness = _SyncHarness(parent)

    harness.sync_key_combo.setCurrentIndex(harness.sync_key_combo.findData("2"))
    harness._propagate_sync_to_modalities(0, "frame", 12.0, 48.0)

    assert harness._updated_windows == [(1, "support", 12.0, 48.0)]


def test_view_sync_selection_clears_when_selected_group_has_no_zoom_targets(qtbot) -> None:
    """Selected zoom group with no zoom-enabled panels should clear stale view links."""
    parent = QtWidgets.QWidget()
    qtbot.addWidget(parent)
    harness = _SyncHarness(parent)

    harness.sync_key_combo.setCurrentIndex(harness.sync_key_combo.findData("2"))
    harness._lazy_sync_modes_state = lambda: {
        0: {"contrast": True, "zoom": True, "playback": True},
        1: {"contrast": True, "zoom": False, "playback": True},
        2: {"contrast": False, "zoom": False, "playback": False},
    }
    harness.link_zoom = True

    harness._apply_view_sync_selection()

    assert harness._view_sync_calls == [("clear",), ("zoom", False), ("pan", False)]
