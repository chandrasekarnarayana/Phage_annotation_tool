"""Tests for contrast dialog."""

from __future__ import annotations

import numpy as np
import pytest

from phage_annotator.ui_qt.widgets.contrast_dialog import ContrastDialog


@pytest.fixture
def dialog(qtbot):
    """Run the dialog workflow."""
    data = np.linspace(0, 255, 256, dtype=np.float32).reshape(16, 16)
    applied = {"values": None}

    def _on_apply(vmin: float, vmax: float) -> None:
        """Handle the on apply helper flow."""
        applied["values"] = (vmin, vmax)

    dlg = ContrastDialog(None, data, 10.0, 200.0, _on_apply)
    qtbot.addWidget(dlg)
    dlg.show()
    return dlg, applied


def test_initial_values(dialog):
    """Verify initial values for the current workflow."""
    dlg, _applied = dialog
    vmin, vmax = dlg.values()
    assert vmin == 10.0
    assert vmax == 200.0


def test_auto_minmax(dialog, qtbot):
    """Verify auto minmax for the current workflow."""
    dlg, _applied = dialog
    dlg._method_combo.setCurrentText("Min/Max")
    dlg._auto_btn.click()
    vmin, vmax = dlg.values()
    assert vmin == 0.0
    assert vmax == 255.0


def test_apply_calls_callback(dialog, qtbot):
    """Verify apply calls callback for the current workflow."""
    dlg, applied = dialog
    dlg._min_spin.setValue(20.0)
    dlg._max_spin.setValue(180.0)
    dlg._apply_btn.click()
    assert applied["values"] == (20.0, 180.0)
