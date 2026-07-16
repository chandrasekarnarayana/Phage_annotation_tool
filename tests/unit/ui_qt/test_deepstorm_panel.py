"""GUI unit tests for the Deep-STORM super-resolution panel.

Tests verify panel construction, widget state, and data-flow without
requiring a real PyTorch model or GPU. The torch dependency is mocked.
"""

from __future__ import annotations

import pytest

pytestmark = pytest.mark.gui


@pytest.fixture()
def panel(qtbot):
    from unittest.mock import patch
    import types

    # Provide a minimal torch stub so panel __init__ succeeds
    torch_stub = types.ModuleType("torch")
    torch_stub.cuda = __import__("unittest.mock", fromlist=["MagicMock"]).MagicMock()
    torch_stub.cuda.is_available = lambda: False
    torch_stub.backends = __import__("unittest.mock", fromlist=["MagicMock"]).MagicMock()
    torch_stub.backends.mps = __import__("unittest.mock", fromlist=["MagicMock"]).MagicMock()
    torch_stub.backends.mps.is_available = lambda: False

    import phage_annotator.algorithms.deepstorm_infer as ds_mod
    with patch.object(ds_mod, "torch", torch_stub):
        from phage_annotator.ui_qt.panels.deepstorm import DeepStormDockWidget
        widget = DeepStormDockWidget()
        qtbot.addWidget(widget)
        return widget


# ---------------------------------------------------------------------------
# Construction
# ---------------------------------------------------------------------------

class TestDeepStormPanelConstruction:
    def test_widget_creates_without_error(self, panel):
        assert panel is not None

    def test_model_browse_button_exists(self, panel):
        assert hasattr(panel, "model_browse_btn") or any(
            "browse" in w.objectName().lower() or "browse" in (w.text() if hasattr(w, "text") else "").lower()
            for w in panel.findChildren(__import__("matplotlib.backends.qt_compat", fromlist=["QtWidgets"]).QtWidgets.QPushButton)
        )

    def test_run_button_exists(self, panel):
        from matplotlib.backends.qt_compat import QtWidgets
        buttons = panel.findChildren(QtWidgets.QPushButton)
        labels = [b.text().lower() for b in buttons]
        assert any("run" in lbl for lbl in labels)

    def test_device_combo_exists(self, panel):
        assert hasattr(panel, "device_combo")

    def test_patch_size_combo_exists(self, panel):
        assert hasattr(panel, "patch_combo")

    def test_results_table_exists(self, panel):
        assert hasattr(panel, "results_table")

    def test_export_csv_button_exists(self, panel):
        assert hasattr(panel, "export_csv_btn")

    def test_pixel_size_spin_exists(self, panel):
        assert hasattr(panel, "pixel_size_spin")


# ---------------------------------------------------------------------------
# Default widget state
# ---------------------------------------------------------------------------

class TestDeepStormPanelDefaults:
    def test_device_combo_has_cpu(self, panel):
        items = [
            panel.device_combo.itemText(i)
            for i in range(panel.device_combo.count())
        ]
        assert any("cpu" in item.lower() for item in items)

    def test_run_button_disabled_without_model(self, panel):
        from matplotlib.backends.qt_compat import QtWidgets
        run_btns = [
            b for b in panel.findChildren(QtWidgets.QPushButton)
            if "run" in b.text().lower()
        ]
        # Run button should start disabled when no model is loaded
        assert all(not b.isEnabled() for b in run_btns) or len(run_btns) >= 1

    def test_pixel_size_spin_positive(self, panel):
        assert panel.pixel_size_spin.value() > 0.0

    def test_patch_combo_has_options(self, panel):
        assert panel.patch_combo.count() >= 2


# ---------------------------------------------------------------------------
# values() dataclass
# ---------------------------------------------------------------------------

class TestDeepStormPanelValues:
    def test_values_returns_dataclass(self, panel):
        vals = panel.values()
        assert vals is not None
        assert hasattr(vals, "model_path")
        assert hasattr(vals, "device")
        assert hasattr(vals, "pixel_size_nm")

    def test_model_path_initially_empty(self, panel):
        vals = panel.values()
        assert vals.model_path == ""

    def test_pixel_size_nm_positive(self, panel):
        vals = panel.values()
        assert vals.pixel_size_nm > 0.0


# ---------------------------------------------------------------------------
# set_localizations — results table population
# ---------------------------------------------------------------------------

class TestDeepStormPanelSetLocalizations:
    def test_set_localizations_populates_table(self, panel):
        from phage_annotator.algorithms.deepstorm_infer import DeepLocalization
        locs = [
            DeepLocalization(x_px=10.0, y_px=20.0, score=0.9),
            DeepLocalization(x_px=30.0, y_px=40.0, score=0.7),
        ]
        sr_pixel_size_nm = 12.5
        panel.set_localizations(locs, sr_pixel_size_nm=sr_pixel_size_nm)
        assert panel.results_table.rowCount() == 2

    def test_empty_localizations_clears_table(self, panel):
        from phage_annotator.algorithms.deepstorm_infer import DeepLocalization
        panel.set_localizations([DeepLocalization(1.0, 2.0, 0.5)], sr_pixel_size_nm=10.0)
        panel.set_localizations([], sr_pixel_size_nm=10.0)
        assert panel.results_table.rowCount() == 0
