"""Unit tests for session package modules without GUI instantiation."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from types import SimpleNamespace
from typing import Optional

import numpy as np

from phage_annotator.core.session_state import RoiSpec, SessionState, ViewState
from phage_annotator.data.display_mapping import DisplayMapping, mapping_from_dict
from phage_annotator.session.commands import SetCropCommand, SetThresholdCommand, command_from_dict
from phage_annotator.session.images import SessionImageMixin
import phage_annotator.session.state as session_state_module
import phage_annotator.session.view as session_view_module


class _Emitter:
    def __init__(self) -> None:
        self.count = 0

    def emit(self) -> None:
        self.count += 1


@dataclass
class _ImageStub:
    id: int
    path: Path
    shape: tuple[int, ...]
    has_time: bool
    has_z: bool
    interpret_3d_as: str = "auto"
    metadata_summary: dict = field(default_factory=dict)
    pixel_size_um: float = 0.0
    ome_axes: Optional[str] = None
    axis_auto_used: bool = False
    axis_auto_mode: Optional[str] = None
    array: Optional[np.ndarray] = None


class _SessionImageHarness(SessionImageMixin):
    def __init__(self, images: list[_ImageStub]) -> None:
        self.state_changed = _Emitter()
        self.annotations_changed = _Emitter()
        self._metadata_cache = {}

        image_states = {}
        for img in images:
            image_states[img.id] = self._build_image_state(img)

        self.session_state = SessionState(
            project_path=None,
            project_save_time=None,
            dirty=False,
            last_folder=None,
            recent_images=[],
            active_primary_id=0,
            active_support_id=0 if len(images) == 1 else 1,
            images=images,
            image_states=image_states,
            annotations={img.id: [] for img in images},
            labels=["Point"],
            current_label="Point",
            annotations_loaded={img.id: False for img in images},
        )


class _SessionViewHarness(session_view_module.SessionViewMixin):
    def __init__(self) -> None:
        self.state_changed = _Emitter()
        self.view_changed = _Emitter()
        self.display_changed = _Emitter()
        self.roi_changed = _Emitter()
        self._undo_stack: list[dict] = []
        self._redo_stack: list[dict] = []
        self.session_state = SimpleNamespace(active_primary_id=0)
        self.view_state = ViewState()
        self.display_mapping = DisplayMapping(0.1, 0.9)


def test_session_images_build_image_state_respects_axis_flags(tmp_path: Path) -> None:
    """Image-state dims should map to canonical (T, Z, Y, X) based on flags."""
    harness = _SessionImageHarness(
        [
            _ImageStub(0, tmp_path / "a.tif", (64, 32), has_time=False, has_z=False),
        ]
    )

    two_d = harness._build_image_state(_ImageStub(0, tmp_path / "a.tif", (64, 32), False, False))
    time_3d = harness._build_image_state(_ImageStub(0, tmp_path / "b.tif", (5, 64, 32), True, False))
    z_3d = harness._build_image_state(_ImageStub(0, tmp_path / "c.tif", (7, 64, 32), False, True))
    four_d = harness._build_image_state(
        _ImageStub(0, tmp_path / "d.tif", (2, 3, 64, 32), True, True)
    )

    assert two_d.dims == (1, 1, 64, 32)
    assert time_3d.dims == (5, 1, 64, 32)
    assert z_3d.dims == (1, 7, 64, 32)
    assert four_d.dims == (2, 3, 64, 32)


def test_session_images_set_images_reindexes_and_resets_state(tmp_path: Path) -> None:
    """Replacing images should rebuild IDs, annotations, and active indices."""
    initial = [_ImageStub(0, tmp_path / "orig.tif", (16, 16), False, False)]
    harness = _SessionImageHarness(initial)

    replacement = [
        _ImageStub(99, tmp_path / "i0.tif", (16, 16), False, False),
        _ImageStub(100, tmp_path / "i1.tif", (16, 16), False, False),
    ]
    harness.set_images(replacement)

    assert [img.id for img in harness.session_state.images] == [0, 1]
    assert sorted(harness.session_state.annotations.keys()) == [0, 1]
    assert harness.session_state.active_primary_id == 0
    assert harness.session_state.active_support_id == 1
    assert harness.state_changed.count == 1
    assert harness.annotations_changed.count == 1


def test_session_commands_crop_and_threshold_undo_redo() -> None:
    """Session commands should support execute/undo/redo and serialization."""
    controller = SimpleNamespace(
        view_state=SimpleNamespace(crop_rect=(0.0, 0.0, 10.0, 10.0)),
        session_state=SimpleNamespace(threshold_configs_by_image={0: {"method": "Otsu"}}),
        display_mapping=DisplayMapping(0.0, 1.0),
    )

    crop_cmd = SetCropCommand(controller, image_id=0, new_crop_rect=(2.0, 2.0, 8.0, 8.0))
    assert crop_cmd.execute() is True
    assert controller.view_state.crop_rect == (2.0, 2.0, 8.0, 8.0)
    assert crop_cmd.undo() is True
    assert controller.view_state.crop_rect == (0.0, 0.0, 10.0, 10.0)
    assert crop_cmd.redo() is True
    assert controller.view_state.crop_rect == (2.0, 2.0, 8.0, 8.0)

    thr_cmd = SetThresholdCommand(controller, image_id=0, new_settings={"method": "Li"})
    assert thr_cmd.execute() is True
    assert controller.session_state.threshold_configs_by_image[0]["method"] == "Li"
    serialized = thr_cmd.to_dict()
    restored = command_from_dict(serialized, controller)
    assert restored is not None
    assert restored.undo() is True
    assert controller.session_state.threshold_configs_by_image[0]["method"] == "Otsu"
    assert restored.redo() is True
    assert controller.session_state.threshold_configs_by_image[0]["method"] == "Li"


def test_session_state_facade_exports_core_dataclasses() -> None:
    """session.state should expose core session dataclasses for compatibility."""
    assert session_state_module.SessionState is SessionState
    state = session_state_module.ViewState()
    assert isinstance(state.roi_spec, RoiSpec)
    assert state.roi_spec.shape == "circle"


def test_view_state_legacy_roi_aliases_roundtrip() -> None:
    """Legacy view-state ROI aliases should stay mapped to roi_spec."""
    state = ViewState()
    state.roi_rect = (11.0, 22.0, 33.0, 44.0)
    state.roi_shape = "box"
    assert state.roi_spec.rect == (11.0, 22.0, 33.0, 44.0)
    assert state.roi_spec.shape == "box"
    # Legacy accessor used by project/session adapters.
    assert state.roi.x == 11.0
    assert state.roi.y == 22.0
    assert state.roi.w == 33.0
    assert state.roi.h == 44.0


def test_display_mapping_legacy_aliases_roundtrip() -> None:
    """Legacy mapping aliases (vmin/vmax/lut_name) should remain stable."""
    mapping = DisplayMapping(0.1, 0.9, lut=3)
    mapping.vmin = 0.2
    mapping.vmax = 0.8
    assert mapping.min_val == 0.2
    assert mapping.max_val == 0.8
    assert mapping.vmin == 0.2
    assert mapping.vmax == 0.8
    assert mapping.lut_name == "3"


def test_mapping_from_dict_accepts_legacy_minmax_keys() -> None:
    """Deserializer should accept old vmin/vmax and min/max keys."""
    m1 = mapping_from_dict({"vmin": 5.0, "vmax": 7.0}, DisplayMapping(0.0, 1.0))
    assert m1.min_val == 5.0
    assert m1.max_val == 7.0
    m2 = mapping_from_dict({"min": 2.5, "max": 9.5}, DisplayMapping(0.0, 1.0))
    assert m2.min_val == 2.5
    assert m2.max_val == 9.5


def test_session_view_mixin_basic_state_mutations() -> None:
    """SessionViewMixin should update view/display fields consistently."""
    harness = _SessionViewHarness()

    harness.set_t(2)
    harness.set_z(3)
    assert harness.view_state.t == 2
    assert harness.view_state.z == 3
    assert harness.view_changed.count >= 2

    harness.set_roi_box(10.0, 20.0, 30.0, 40.0)
    assert harness.view_state.roi_spec.shape == "box"
    assert harness.view_state.roi_spec.rect == (10.0, 20.0, 30.0, 40.0)
    harness.clear_roi()
    assert harness.view_state.roi_spec.shape == "none"

    harness.set_display_mapping(0.2, 0.8, gamma=1.1)
    harness.set_lut(4)
    harness.set_invert(True)
    harness.set_gamma(0.9)

    mapping = harness.display_mapping.mapping_for(0, "frame")
    assert mapping.min_val == 0.2
    assert mapping.max_val == 0.8
    assert mapping.lut == 4
    assert mapping.invert is True
    assert mapping.gamma == 0.9
    assert harness.display_changed.count >= 1
