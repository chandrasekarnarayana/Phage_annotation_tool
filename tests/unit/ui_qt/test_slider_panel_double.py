"""Tests for SliderPanelDouble widget."""

from __future__ import annotations

from phage_annotator.ui_qt.widgets.slider_panel_double import SliderPanelDouble


def test_slider_range_updates(qtbot):
    slider = SliderPanelDouble()
    qtbot.addWidget(slider)
    slider.setRange(0.0, 10.0)
    slider.setValues(2.0, 8.0)
    assert slider.values() == (2.0, 8.0)


def test_slider_clamps_values(qtbot):
    slider = SliderPanelDouble()
    qtbot.addWidget(slider)
    slider.setRange(0.0, 5.0)
    slider.setValues(-2.0, 12.0)
    assert slider.values() == (0.0, 5.0)
