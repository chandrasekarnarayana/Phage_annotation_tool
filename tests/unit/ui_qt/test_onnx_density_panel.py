"""GUI unit tests for the ONNX density prediction panel.

Tests verify panel construction, widget state, and UI data-flow without
requiring a real ONNX model, GPU, or onnxruntime installation.
The onnxruntime dependency is mocked throughout.
"""

from __future__ import annotations

import pytest

pytestmark = pytest.mark.gui


@pytest.fixture()
def panel(qtbot):
    import phage_annotator.algorithms.onnx_infer as onnx_mod
    from unittest.mock import patch

    with patch.object(onnx_mod, "_ORT_AVAILABLE", False):
        from phage_annotator.ui_qt.panels.onnx_density import OnnxDensityPanel
        widget = OnnxDensityPanel()
        qtbot.addWidget(widget)
        return widget


# ---------------------------------------------------------------------------
# Construction
# ---------------------------------------------------------------------------

class TestOnnxDensityPanelConstruction:
    def test_widget_creates_without_error(self, panel):
        assert panel is not None

    def test_run_button_exists(self, panel):
        from matplotlib.backends.qt_compat import QtWidgets
        buttons = panel.findChildren(QtWidgets.QPushButton)
        labels = [b.text().lower() for b in buttons]
        assert any("run" in lbl for lbl in labels)

    def test_model_path_edit_exists(self, panel):
        assert hasattr(panel, "model_path_edit")

    def test_provider_combo_exists(self, panel):
        assert hasattr(panel, "provider_combo")

    def test_tile_size_spin_exists(self, panel):
        assert hasattr(panel, "tile_size_spin")

    def test_overlap_spin_exists(self, panel):
        assert hasattr(panel, "overlap_spin")

    def test_progress_bar_exists(self, panel):
        from matplotlib.backends.qt_compat import QtWidgets
        bars = panel.findChildren(QtWidgets.QProgressBar)
        assert len(bars) >= 1

    def test_results_count_label_exists(self, panel):
        assert hasattr(panel, "count_total_lbl") or hasattr(panel, "result_count_lbl")


# ---------------------------------------------------------------------------
# Default widget state
# ---------------------------------------------------------------------------

class TestOnnxDensityPanelDefaults:
    def test_provider_combo_has_cpu_option(self, panel):
        items = [
            panel.provider_combo.itemText(i)
            for i in range(panel.provider_combo.count())
        ]
        assert any("CPU" in item for item in items)

    def test_tile_size_positive(self, panel):
        assert panel.tile_size_spin.value() > 0

    def test_overlap_non_negative(self, panel):
        assert panel.overlap_spin.value() >= 0

    def test_model_path_initially_empty(self, panel):
        assert panel.model_path_edit.text() == ""

    def test_run_button_disabled_without_model(self, panel):
        from matplotlib.backends.qt_compat import QtWidgets
        run_btns = [
            b for b in panel.findChildren(QtWidgets.QPushButton)
            if "run" in b.text().lower()
        ]
        # Without a model loaded, run should be disabled
        assert any(not b.isEnabled() for b in run_btns)

    def test_count_scale_positive(self, panel):
        assert hasattr(panel, "count_scale_spin")
        assert panel.count_scale_spin.value() > 0.0


# ---------------------------------------------------------------------------
# Provider population
# ---------------------------------------------------------------------------

class TestOnnxDensityProviderCombo:
    def test_always_contains_cpu(self, panel):
        found = False
        for i in range(panel.provider_combo.count()):
            if "CPU" in panel.provider_combo.itemText(i):
                found = True
                break
        assert found

    def test_combo_count_at_least_one(self, panel):
        assert panel.provider_combo.count() >= 1


# ---------------------------------------------------------------------------
# Export controls
# ---------------------------------------------------------------------------

class TestOnnxDensityExportControls:
    def test_export_tiff_button_exists(self, panel):
        from matplotlib.backends.qt_compat import QtWidgets
        buttons = panel.findChildren(QtWidgets.QPushButton)
        labels = [b.text().lower() for b in buttons]
        assert any("tiff" in lbl or "export" in lbl for lbl in labels)

    def test_export_csv_button_exists(self, panel):
        from matplotlib.backends.qt_compat import QtWidgets
        buttons = panel.findChildren(QtWidgets.QPushButton)
        labels = [b.text().lower() for b in buttons]
        assert any("csv" in lbl for lbl in labels)
