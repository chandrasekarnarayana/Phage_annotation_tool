"""Tests for canvas header overlay text semantics."""

from __future__ import annotations

from types import SimpleNamespace

import numpy as np

from phage_annotator.ui_qt.rendering.renderer import RenderingMixin


class _Harness(RenderingMixin):
    def _slice_indices(self, _img):
        return int(self.t_slider.value()), int(self.z_slider.value())


class _Slider:
    def __init__(self, value: int, maximum: int) -> None:
        self._value = int(value)
        self._maximum = int(maximum)

    def value(self) -> int:
        return self._value

    def maximum(self) -> int:
        return self._maximum


def test_canvas_header_frame_slice_mode() -> None:
    harness = _Harness()
    harness.primary_image = SimpleNamespace(array=np.zeros((24, 15, 16, 16)))
    harness.t_slider = _Slider(4, 23)
    harness.z_slider = _Slider(2, 14)
    harness.annotate_target = "frame"
    harness.annotation_scope = "current"
    text = harness._build_canvas_header_text()
    assert text == "Frame T=5 Z=3 | Slice Annotation (Current Z)"


def test_canvas_header_mean_stack_mode() -> None:
    harness = _Harness()
    harness.primary_image = SimpleNamespace(array=np.zeros((24, 15, 16, 16)))
    harness.t_slider = _Slider(0, 23)
    harness.z_slider = _Slider(0, 14)
    harness.annotate_target = "mean"
    harness.annotation_scope = "all"
    text = harness._build_canvas_header_text()
    assert text == "Mean Projection (Z=1-15) | Stack Annotation (All Z)"
