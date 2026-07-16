"""ROI dock widget construction helpers."""

from __future__ import annotations

from matplotlib.backends.qt_compat import QtWidgets

from phage_annotator.ui_qt.utils.dock_roi_widgets_impl import (
    make_roi_manager_widget,
    make_results_widget,
    make_recorder_widget,
    make_hist_widget,
    make_profile_widget,
    make_orthoview_widget,
    make_smlm_widget,
    make_threshold_widget,
    make_particles_widget,
    make_channel_controls_widget,
    make_deepstorm_widget,
    make_onnx_density_widget,
)

def make_roi_widget(self) -> QtWidgets.QWidget:
    """Create roi widget for the current workflow."""
    roi_widget = QtWidgets.QWidget()
    root_layout = QtWidgets.QVBoxLayout(roi_widget)
    root_layout.setContentsMargins(8, 8, 8, 8)
    root_layout.setSpacing(8)

    scroll = QtWidgets.QScrollArea(roi_widget)
    scroll.setWidgetResizable(True)
    scroll_content = QtWidgets.QWidget(scroll)
    layout = QtWidgets.QVBoxLayout(scroll_content)
    layout.setContentsMargins(0, 0, 0, 0)
    layout.setSpacing(8)

    summary_lbl = QtWidgets.QLabel("ROI Controls")
    summary_lbl.setStyleSheet("font-weight: 700; color: #1f2937;")
    layout.addWidget(summary_lbl)
    helper_lbl = QtWidgets.QLabel(
        "Edit ROI geometry, crop bounds, and auto-ROI from this panel."
    )
    helper_lbl.setWordWrap(True)
    helper_lbl.setStyleSheet("color: #4b5563;")
    layout.addWidget(helper_lbl)

    roi_group = QtWidgets.QGroupBox("ROI Geometry")
    roi_grid = QtWidgets.QGridLayout(roi_group)
    roi_grid.setHorizontalSpacing(6)
    roi_grid.setVerticalSpacing(4)

    roi_shape_combo = QtWidgets.QComboBox(roi_group)
    roi_shape_combo.addItem("Rectangle", "box")
    roi_shape_combo.addItem("Circle", "circle")
    roi_shape_combo.setCurrentIndex(0 if str(getattr(self, "roi_shape", "box")) == "box" else 1)

    roi_x_spin = QtWidgets.QDoubleSpinBox(roi_group)
    roi_y_spin = QtWidgets.QDoubleSpinBox(roi_group)
    roi_w_spin = QtWidgets.QDoubleSpinBox(roi_group)
    roi_h_spin = QtWidgets.QDoubleSpinBox(roi_group)
    for spin in (roi_x_spin, roi_y_spin, roi_w_spin, roi_h_spin):
        spin.setRange(0.0, 1_000_000.0)
        spin.setDecimals(1)
        spin.setSingleStep(5.0)
    rx, ry, rw, rh = tuple(getattr(self, "roi_rect", (0.0, 0.0, 0.0, 0.0)))
    roi_x_spin.setValue(float(rx))
    roi_y_spin.setValue(float(ry))
    roi_w_spin.setValue(float(rw))
    roi_h_spin.setValue(float(rh))

    def _sync_roi_fields() -> None:
        """Synchronize roi fields for the current workflow."""
        x, y, w, h = tuple(getattr(self, "roi_rect", (0.0, 0.0, 0.0, 0.0)))
        for spin, val in (
            (roi_x_spin, x),
            (roi_y_spin, y),
            (roi_w_spin, w),
            (roi_h_spin, h),
        ):
            spin.blockSignals(True)
            spin.setValue(float(val))
            spin.blockSignals(False)
        idx = roi_shape_combo.findData(str(getattr(self, "roi_shape", "box")))
        if idx >= 0:
            roi_shape_combo.blockSignals(True)
            roi_shape_combo.setCurrentIndex(idx)
            roi_shape_combo.blockSignals(False)

    def _apply_roi_fields() -> None:
        """Apply roi fields for the current workflow."""
        rect = (
            float(roi_x_spin.value()),
            float(roi_y_spin.value()),
            float(roi_w_spin.value()),
            float(roi_h_spin.value()),
        )
        if hasattr(self, "_set_roi_rect"):
            self._set_roi_rect(rect)
        else:
            self.roi_rect = rect
        if hasattr(self, "_request_ui_refresh"):
            self._request_ui_refresh("roi_dock")

    roi_shape_combo.currentIndexChanged.connect(
        lambda _idx: (
            self._set_roi_shape(str(roi_shape_combo.currentData() or "box"))
            if hasattr(self, "_set_roi_shape")
            else None,
            self._request_ui_refresh("roi_dock") if hasattr(self, "_request_ui_refresh") else None,
        )
    )

    roi_apply_btn = QtWidgets.QPushButton("Apply ROI")
    roi_apply_btn.clicked.connect(_apply_roi_fields)
    roi_sync_btn = QtWidgets.QPushButton("Sync from Canvas")
    roi_sync_btn.clicked.connect(_sync_roi_fields)
    roi_clear_btn = QtWidgets.QPushButton("Clear ROI")
    roi_clear_btn.clicked.connect(self._clear_roi)
    roi_full_btn = QtWidgets.QPushButton("Full Image")
    roi_full_btn.clicked.connect(self._reset_roi)

    roi_grid.addWidget(QtWidgets.QLabel("Shape"), 0, 0)
    roi_grid.addWidget(roi_shape_combo, 0, 1, 1, 3)
    roi_grid.addWidget(QtWidgets.QLabel("X"), 1, 0)
    roi_grid.addWidget(roi_x_spin, 1, 1)
    roi_grid.addWidget(QtWidgets.QLabel("Y"), 1, 2)
    roi_grid.addWidget(roi_y_spin, 1, 3)
    roi_grid.addWidget(QtWidgets.QLabel("W"), 2, 0)
    roi_grid.addWidget(roi_w_spin, 2, 1)
    roi_grid.addWidget(QtWidgets.QLabel("H"), 2, 2)
    roi_grid.addWidget(roi_h_spin, 2, 3)
    roi_grid.addWidget(roi_apply_btn, 3, 0, 1, 2)
    roi_grid.addWidget(roi_sync_btn, 3, 2, 1, 2)
    roi_grid.addWidget(roi_clear_btn, 4, 0, 1, 2)
    roi_grid.addWidget(roi_full_btn, 4, 2, 1, 2)
    layout.addWidget(roi_group)

    crop_group = QtWidgets.QGroupBox("Crop")
    crop_grid = QtWidgets.QGridLayout(crop_group)
    crop_grid.setHorizontalSpacing(6)
    crop_grid.setVerticalSpacing(4)
    crop_x_spin = QtWidgets.QDoubleSpinBox(crop_group)
    crop_y_spin = QtWidgets.QDoubleSpinBox(crop_group)
    crop_w_spin = QtWidgets.QDoubleSpinBox(crop_group)
    crop_h_spin = QtWidgets.QDoubleSpinBox(crop_group)
    for spin in (crop_x_spin, crop_y_spin, crop_w_spin, crop_h_spin):
        spin.setRange(0.0, 1_000_000.0)
        spin.setDecimals(1)
        spin.setSingleStep(5.0)

    def _sync_crop_fields() -> None:
        """Synchronize crop fields for the current workflow."""
        rect = tuple(getattr(self, "crop_rect", (0.0, 0.0, 0.0, 0.0)) or (0.0, 0.0, 0.0, 0.0))
        for spin, val in (
            (crop_x_spin, rect[0]),
            (crop_y_spin, rect[1]),
            (crop_w_spin, rect[2]),
            (crop_h_spin, rect[3]),
        ):
            spin.blockSignals(True)
            spin.setValue(float(val))
            spin.blockSignals(False)

    def _apply_crop_fields() -> None:
        """Apply crop fields for the current workflow."""
        self.crop_rect = (
            float(crop_x_spin.value()),
            float(crop_y_spin.value()),
            float(crop_w_spin.value()),
            float(crop_h_spin.value()),
        )
        if hasattr(self, "_request_ui_refresh"):
            self._request_ui_refresh("roi_dock")

    _sync_crop_fields()
    crop_apply_btn = QtWidgets.QPushButton("Apply Crop")
    crop_apply_btn.clicked.connect(_apply_crop_fields)
    crop_sync_btn = QtWidgets.QPushButton("Sync")
    crop_sync_btn.clicked.connect(_sync_crop_fields)
    crop_full_btn = QtWidgets.QPushButton("Full Crop")
    crop_full_btn.clicked.connect(lambda: (self._reset_crop(initial=True), _sync_crop_fields()))
    crop_clear_btn = QtWidgets.QPushButton("Clear Crop")
    crop_clear_btn.clicked.connect(lambda: (self._reset_crop(initial=False), _sync_crop_fields()))

    crop_grid.addWidget(QtWidgets.QLabel("X"), 0, 0)
    crop_grid.addWidget(crop_x_spin, 0, 1)
    crop_grid.addWidget(QtWidgets.QLabel("Y"), 0, 2)
    crop_grid.addWidget(crop_y_spin, 0, 3)
    crop_grid.addWidget(QtWidgets.QLabel("W"), 1, 0)
    crop_grid.addWidget(crop_w_spin, 1, 1)
    crop_grid.addWidget(QtWidgets.QLabel("H"), 1, 2)
    crop_grid.addWidget(crop_h_spin, 1, 3)
    crop_grid.addWidget(crop_apply_btn, 2, 0, 1, 2)
    crop_grid.addWidget(crop_sync_btn, 2, 2, 1, 2)
    crop_grid.addWidget(crop_full_btn, 3, 0, 1, 2)
    crop_grid.addWidget(crop_clear_btn, 3, 2, 1, 2)
    layout.addWidget(crop_group)

    auto_group = QtWidgets.QGroupBox("Auto ROI")
    auto_grid = QtWidgets.QGridLayout(auto_group)
    auto_shape_combo = QtWidgets.QComboBox(auto_group)
    auto_shape_combo.addItems(["box", "circle", "auto"])
    auto_shape_combo.setCurrentText(str(self._settings.value("autoRoiShape", "box", type=str)))
    auto_mode_combo = QtWidgets.QComboBox(auto_group)
    auto_mode_combo.addItems(["W/H", "Area"])
    auto_mode_combo.setCurrentText(str(self._settings.value("autoRoiMode", "W/H", type=str)))
    auto_w_spin = QtWidgets.QSpinBox(auto_group)
    auto_h_spin = QtWidgets.QSpinBox(auto_group)
    auto_area_spin = QtWidgets.QSpinBox(auto_group)
    for spin in (auto_w_spin, auto_h_spin, auto_area_spin):
        spin.setRange(10, 1_000_000)
        spin.setSingleStep(10)
    auto_w_spin.setValue(int(self._settings.value("autoRoiW", 100, type=int)))
    auto_h_spin.setValue(int(self._settings.value("autoRoiH", 100, type=int)))
    auto_area_spin.setValue(int(self._settings.value("autoRoiArea", 100 * 100, type=int)))

    auto_wh_widget = QtWidgets.QWidget(auto_group)
    auto_wh_layout = QtWidgets.QHBoxLayout(auto_wh_widget)
    auto_wh_layout.setContentsMargins(0, 0, 0, 0)
    auto_wh_layout.setSpacing(6)
    auto_wh_layout.addWidget(QtWidgets.QLabel("W"))
    auto_wh_layout.addWidget(auto_w_spin)
    auto_wh_layout.addWidget(QtWidgets.QLabel("H"))
    auto_wh_layout.addWidget(auto_h_spin)
    auto_area_widget = QtWidgets.QWidget(auto_group)
    auto_area_layout = QtWidgets.QHBoxLayout(auto_area_widget)
    auto_area_layout.setContentsMargins(0, 0, 0, 0)
    auto_area_layout.setSpacing(6)
    auto_area_layout.addWidget(QtWidgets.QLabel("Area"))
    auto_area_layout.addWidget(auto_area_spin)

    def _persist_auto() -> None:
        """Handle the persist auto helper flow."""
        self._settings.setValue("autoRoiShape", auto_shape_combo.currentText())
        self._settings.setValue("autoRoiMode", auto_mode_combo.currentText())
        self._settings.setValue("autoRoiW", int(auto_w_spin.value()))
        self._settings.setValue("autoRoiH", int(auto_h_spin.value()))
        self._settings.setValue("autoRoiArea", int(auto_area_spin.value()))

    def _update_auto_mode() -> None:
        """Update auto mode for the current workflow."""
        mode = str(auto_mode_combo.currentText())
        auto_wh_widget.setVisible(mode == "W/H")
        auto_area_widget.setVisible(mode == "Area")
        _persist_auto()

    auto_shape_combo.currentTextChanged.connect(lambda _v: _persist_auto())
    auto_mode_combo.currentTextChanged.connect(lambda _v: _update_auto_mode())
    auto_w_spin.valueChanged.connect(lambda _v: _persist_auto())
    auto_h_spin.valueChanged.connect(lambda _v: _persist_auto())
    auto_area_spin.valueChanged.connect(lambda _v: _persist_auto())
    _update_auto_mode()

    auto_run_btn = QtWidgets.QPushButton("Run Auto ROI")

    def _run_auto_from_dock() -> None:
        # Mirror dock values into primary controls if present so core auto-ROI logic
        # remains centralized and consistent.
        """Run auto from dock for the current workflow."""
        for attr, value in (
            ("auto_roi_shape_combo", auto_shape_combo.currentText()),
            ("auto_roi_mode_combo", auto_mode_combo.currentText()),
        ):
            widget = getattr(self, attr, None)
            if widget is not None and hasattr(widget, "setCurrentText"):
                widget.blockSignals(True)
                widget.setCurrentText(str(value))
                widget.blockSignals(False)
        for attr, value in (
            ("auto_roi_w_spin", int(auto_w_spin.value())),
            ("auto_roi_h_spin", int(auto_h_spin.value())),
            ("auto_roi_area_spin", int(auto_area_spin.value())),
        ):
            widget = getattr(self, attr, None)
            if widget is not None and hasattr(widget, "setValue"):
                widget.blockSignals(True)
                widget.setValue(int(value))
                widget.blockSignals(False)
        if hasattr(self, "_run_auto_roi"):
            self._run_auto_roi()

    auto_run_btn.clicked.connect(_run_auto_from_dock)

    auto_grid.addWidget(QtWidgets.QLabel("Shape"), 0, 0)
    auto_grid.addWidget(auto_shape_combo, 0, 1)
    auto_grid.addWidget(QtWidgets.QLabel("Size mode"), 1, 0)
    auto_grid.addWidget(auto_mode_combo, 1, 1)
    auto_grid.addWidget(auto_wh_widget, 2, 0, 1, 2)
    auto_grid.addWidget(auto_area_widget, 3, 0, 1, 2)
    auto_grid.addWidget(auto_run_btn, 4, 0, 1, 2)
    layout.addWidget(auto_group)

    manager_group = QtWidgets.QGroupBox("ROI Manager")
    manager_layout = QtWidgets.QVBoxLayout(manager_group)
    open_manager_btn = QtWidgets.QPushButton("Open ROI Manager")
    open_manager_btn.clicked.connect(lambda: self.open_panel("roi_manager", reason="roi_dock"))
    open_page_btn = QtWidgets.QPushButton("Open ROI Page")
    open_page_btn.setToolTip("Focus the workflow sidebar on ROI controls.")
    open_page_btn.clicked.connect(
        lambda: (
            self._set_sidebar_mode(self._sidebar_action_index_for_label("ROI"))
            if self._sidebar_action_index_for_label("ROI") >= 0
            else None
        )
    )
    manager_layout.addWidget(open_manager_btn)
    manager_layout.addWidget(open_page_btn)
    layout.addWidget(manager_group)

    layout.addStretch(1)
    scroll.setWidget(scroll_content)
    root_layout.addWidget(scroll)
    return roi_widget
