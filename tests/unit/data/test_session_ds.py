from __future__ import annotations

from dataclasses import dataclass, field
from types import SimpleNamespace

import numpy as np

from phage_annotator.core.session_state import RoiSpec
from phage_annotator.data.session_ds import SessionDataSource


@dataclass
class _ImageState:
    pixel_size_um: float = 0.25


@dataclass
class _LazyImageStub:
    array: np.ndarray
    id: int = 0
    name: str = "img"
    has_time: bool = True
    has_z: bool = True
    axis_info: dict = field(default_factory=dict)

    @property
    def shape(self):
        return self.array.shape

    @property
    def dtype(self):
        return self.array.dtype

    def get_full_array(self) -> np.ndarray:
        return self.array


def _make_session() -> SimpleNamespace:
    primary = _LazyImageStub(
        np.arange(2 * 3 * 4 * 5, dtype=np.float32).reshape(2, 3, 4, 5),
        id=0,
        axis_info={"tzyx": (2, 3, 4, 5)},
    )
    support = _LazyImageStub(np.ones((2, 3, 4, 5), dtype=np.float32), id=1, name="support")
    kp = SimpleNamespace(
        id="ann-1",
        image_id=0,
        image_name="img",
        t=0,
        z=1,
        y=2.0,
        x=3.0,
        label="Phage",
        color="#ff0",
        selected=True,
    )
    return SimpleNamespace(
        ring_buffer=None,
        proj_cache=None,
        session_state=SimpleNamespace(
            active_primary_id=0,
            active_support_id=1,
            images=[primary, support],
            annotations={0: [kp]},
            image_states={0: _ImageState()},
        ),
        view_state=SimpleNamespace(
            roi_spec=RoiSpec((1, 2, 4, 6), "box"),
        ),
    )


def test_session_ds_shape_and_frame_extraction() -> None:
    ds = SessionDataSource(_make_session())

    assert ds.get_shape() == (2, 3, 4, 5)
    frame = ds.get_frame(1, 2, crop_rect=(1, 1, 3, 2), downsample=1)

    assert frame.data.shape == (2, 3)
    assert frame.t_idx == 1
    assert frame.z_idx == 2


def test_session_ds_annotations_transform_and_selection() -> None:
    ds = SessionDataSource(_make_session())

    anns = ds.get_annotations(t_idx=0, z_idx=0, crop_rect=(0, 0, 10, 10), downsample=1, selected_only=True)

    assert len(anns) == 1
    assert anns[0].label == "Phage"
    assert anns[0].selected is True
    assert anns[0].metadata["id"] == ds._session.session_state.annotations[0][0].id


def test_session_ds_roi_overlay_and_calibration() -> None:
    ds = SessionDataSource(_make_session())

    overlays = ds.get_roi_overlays(crop_rect=(0, 0, 20, 20), downsample=2)
    calibration = ds.get_calibration()

    assert overlays[0][0] == "box"
    assert calibration.calibrated is True
    assert calibration.pixel_size_um == 0.25
