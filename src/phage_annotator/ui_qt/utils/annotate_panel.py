"""Extracted method group 4 for UiExtrasMixin."""

from __future__ import annotations

from pathlib import Path
from typing import List, Set, Tuple

from matplotlib.backends.qt_compat import QtCore, QtGui, QtWidgets

from phage_annotator.ui_qt.services.action_logger import get_action_logger

from phage_annotator.ui_qt.models.lazy_loader import (
    LAZY_LOADER_FILE_FILTER,
    LAZY_LOADER_OPEN_FILES_TITLE,
    LAZY_LOADER_OPEN_FOLDER_TITLE,
    LAZY_TABLE_COLUMN_GROUP,
    LAZY_TABLE_COLUMN_NAME,
    LAZY_TABLE_COLUMN_ANNOTATION_FILE,
    LAZY_TABLE_COLUMN_ANNOTATION_MODE,
    LAZY_TABLE_COLUMN_POINTS,
    LAZY_TABLE_COLUMN_PROJECTION,
    LAZY_TABLE_COLUMN_SHOW,
    LAZY_TABLE_COLUMN_SOURCE,
    LAZY_TABLE_COLUMN_SYNC_CONTRAST,
    LAZY_TABLE_COLUMN_SYNC_TIME,
    LAZY_TABLE_COLUMN_SYNC_VIEW,
    LAZY_TABLE_COLUMN_TABLE,
    LazyTableRowSpec,
    normalize_lazy_sync_groups,
    iter_tiff_paths,
)
from phage_annotator.ui_qt.utils.ui_extra_annotations import (
    UiAnnotationViewsMixin,
    _LogicalVisibilityLabel,
)
from phage_annotator.ui_qt.utils.ui_extra_refresh import UiRefreshMixin
from phage_annotator.ui_qt.utils.ui_extra_tooltips import UiTooltipMixin
from phage_annotator.ui_qt.utils.iconography import right_sidebar_icon, tool_icon, workflow_sidebar_icon
from phage_annotator.ui_qt.utils.image_io import read_metadata
from phage_annotator.ui_qt.utils.sidebar_manager import SidebarLayoutConfig, SidebarManager
from phage_annotator.tools import Tool, ToolCallbacks, ToolRouter

PRIMARY_RIGHT_SIDEBAR_PANELS = (
    "annotations",
    "review_queue",
    "advanced_settings",
    "advanced_analysis",
    "qc_issues",
)
SUPPLEMENTAL_RIGHT_SIDEBAR_PANELS = (
    "status_details",
)
ALL_RIGHT_SIDEBAR_PANELS = PRIMARY_RIGHT_SIDEBAR_PANELS + SUPPLEMENTAL_RIGHT_SIDEBAR_PANELS



class AnnotatePanelMixin:
    """Method group 4 extracted from UiExtrasMixin."""

    def _build_annotate_panel(self) -> QtWidgets.QWidget:
        """Build annotate panel for the current workflow."""
        panel = QtWidgets.QWidget()
        panel.setObjectName("annotate_sidebar_panel")
        panel.setStyleSheet(
            "#annotate_sidebar_panel QGroupBox {"
            " margin-top: 10px; border: 1px solid #e4e7eb; border-radius: 5px; padding-top: 4px; }"
            "#annotate_sidebar_panel QGroupBox::title {"
            " subcontrol-origin: margin; left: 8px; padding: 0 4px; color: #263238; font-weight: 600; }"
            "#annotate_sidebar_panel QComboBox, #annotate_sidebar_panel QLineEdit { min-height: 24px; }"
            "#annotate_sidebar_panel QCheckBox, #annotate_sidebar_panel QRadioButton { min-height: 22px; }"
        )
        layout = QtWidgets.QVBoxLayout(panel)
        layout.setContentsMargins(10, 10, 10, 10)
        layout.setSpacing(10)
        intro_lbl = QtWidgets.QLabel("Target, label, scope, and tool.")
        intro_lbl.setWordWrap(True)
        intro_lbl.setStyleSheet("color: #546e7a;")
        layout.addWidget(intro_lbl)

        quick_group = QtWidgets.QGroupBox("Quick panels")
        quick_layout = QtWidgets.QGridLayout(quick_group)
        quick_layout.setContentsMargins(8, 8, 8, 8)
        quick_layout.setHorizontalSpacing(6)
        quick_layout.setVerticalSpacing(6)
        open_annotations_btn = QtWidgets.QPushButton("Annotation Table")
        open_annotations_btn.setToolTip("Open the annotation table to inspect or edit the current annotation set.")
        open_annotations_btn.clicked.connect(
            lambda: self.open_panel("annotations", reason="annotate_sidebar")
        )
        open_review_btn = QtWidgets.QPushButton("Assist")
        open_review_btn.setToolTip("Open assist review tools for suggestions and decisions.")
        open_review_btn.clicked.connect(
            lambda: self.open_panel("review_queue", reason="annotate_sidebar")
        )
        quick_layout.addWidget(open_annotations_btn, 0, 0)
        quick_layout.addWidget(open_review_btn, 0, 1)
        layout.addWidget(quick_group)

        target_group = QtWidgets.QGroupBox("1. Write target")
        target_layout = QtWidgets.QVBoxLayout(target_group)
        target_layout.setContentsMargins(8, 8, 8, 8)
        target_layout.setSpacing(6)
        target_help_lbl = QtWidgets.QLabel(
            "Choose the canvas view you are annotating. This list updates from the views currently visible on the canvas."
        )
        target_help_lbl.setWordWrap(True)
        target_help_lbl.setStyleSheet("color: #546e7a;")
        target_layout.addWidget(target_help_lbl)
        self.annotate_target_combo = QtWidgets.QComboBox(target_group)
        self.annotate_target_combo.setToolTip(
            "Choose the visible canvas view/modality where new points will be written. Hidden views are removed from this list."
        )
        target_layout.addWidget(self.annotate_target_combo)
        self.target_state_badge_lbl = QtWidgets.QLabel("Write target: -")
        self.target_state_badge_lbl.setStyleSheet(
            "background:#e8f0fe; color:#1d4e89; padding:3px 6px; border-radius:4px; font-weight:600;"
        )
        target_layout.addWidget(self.target_state_badge_lbl)
        self.annotate_enabled_chk = QtWidgets.QCheckBox("Enable click annotation", target_group)
        self.annotate_enabled_chk.setChecked(
            bool(self._settings.value("annotationClickEnabled", True, type=bool))
        )
        self.annotate_enabled_chk.setToolTip(
            "When enabled, left-clicking on the selected target view adds or removes annotation points."
        )
        self.annotate_enabled_chk.toggled.connect(
            lambda checked: self._settings.setValue("annotationClickEnabled", bool(checked))
        )
        target_layout.addWidget(self.annotate_enabled_chk)
        self.target_unavailable_hint_lbl = _LogicalVisibilityLabel("")
        self.target_unavailable_hint_lbl.setWordWrap(True)
        self.target_unavailable_hint_lbl.setStyleSheet("color: #546e7a; font-style: italic;")
        self.target_unavailable_hint_lbl.setVisible(False)
        target_layout.addWidget(self.target_unavailable_hint_lbl)
        layout.addWidget(target_group)

        label_group = QtWidgets.QGroupBox("2. Label")
        label_layout = QtWidgets.QVBoxLayout(label_group)
        label_layout.setContentsMargins(8, 8, 8, 8)
        label_layout.setSpacing(6)
        self.label_buttons = QtWidgets.QButtonGroup()
        # P3.5: Guard against empty label lists
        labels_to_display = self.labels if self.labels else ["Point", "Region"]
        for label in labels_to_display:
            btn = QtWidgets.QRadioButton(label)
            if label == self.current_label:
                btn.setChecked(True)
            self.label_buttons.addButton(btn)
            label_layout.addWidget(btn)
        layout.addWidget(label_group)

        scope_group = QtWidgets.QGroupBox("3. Scope")
        scope_layout = QtWidgets.QVBoxLayout(scope_group)
        scope_layout.setContentsMargins(8, 8, 8, 8)
        scope_layout.setSpacing(6)
        self.scope_group = QtWidgets.QButtonGroup()
        for label in ["Current slice", "All slices"]:
            btn = QtWidgets.QRadioButton(label)
            scope_value = str(getattr(self, "annotation_scope", "current"))
            if (scope_value == "all" and label == "All slices") or (
                scope_value != "all" and label == "Current slice"
            ):
                btn.setChecked(True)
            self.scope_group.addButton(btn)
            scope_layout.addWidget(btn)
        scope_buttons = self.scope_group.buttons()
        if len(scope_buttons) > 1:
            self._install_delayed_micro_help(
                scope_buttons[1],
                "Annotations will be applied to all Z planes.\nUse with caution.",
            )
        layout.addWidget(scope_group)

        self._annotate_roi_embedded = False
        roi_shortcuts_group = QtWidgets.QGroupBox("4. ROI")
        roi_shortcuts_layout = QtWidgets.QVBoxLayout(roi_shortcuts_group)
        roi_shortcuts_layout.setContentsMargins(8, 8, 8, 8)
        roi_shortcuts_layout.setSpacing(6)
        roi_hint_lbl = QtWidgets.QLabel(
            "ROI controls were moved to the ROI panel. Open it here for ROI/crop/edit tools."
        )
        roi_hint_lbl.setWordWrap(True)
        roi_hint_lbl.setStyleSheet("color: #546e7a;")
        roi_shortcuts_layout.addWidget(roi_hint_lbl)
        roi_open_btn_row = QtWidgets.QHBoxLayout()
        roi_open_btn = QtWidgets.QPushButton("Open ROI Controls")
        roi_open_btn.clicked.connect(lambda: self.open_panel("roi", reason="annotate_sidebar"))
        roi_manager_btn = QtWidgets.QPushButton("Open ROI Manager")
        roi_manager_btn.clicked.connect(lambda: self.open_panel("roi_manager", reason="annotate_sidebar"))
        roi_open_btn_row.addWidget(roi_open_btn)
        roi_open_btn_row.addWidget(roi_manager_btn)
        roi_open_btn_row.addStretch(1)
        roi_shortcuts_layout.addLayout(roi_open_btn_row)
        layout.addWidget(roi_shortcuts_group)

        tool_group = QtWidgets.QGroupBox("5. Tools")
        tool_layout = QtWidgets.QVBoxLayout(tool_group)
        tool_layout.setContentsMargins(8, 8, 8, 8)
        tool_layout.setSpacing(6)
        self.tool_label = QtWidgets.QLabel("Tool: Annotate")
        tool_layout.addWidget(self.tool_label)
        tool_help_lbl = QtWidgets.QLabel("Toolbar and shortcuts control the active tool.")
        tool_help_lbl.setWordWrap(True)
        tool_help_lbl.setStyleSheet("color: #546e7a;")
        tool_layout.addWidget(tool_help_lbl)
        
        # ARCHITECTURAL FIX: Add profile_mode_chk to prevent AttributeError in _set_profile_mode()
        # This checkbox enables click-two-points line profile mode
        # Phase 2D: This should be part of ToolState dataclass
        self.profile_mode_chk = QtWidgets.QCheckBox("Profile mode (click two points)")
        self.profile_mode_chk.setChecked(False)
        self._install_delayed_micro_help(
            self.profile_mode_chk,
            "Profile mode:\nClick two points to extract an intensity profile\nalong the line between them.",
        )
        tool_layout.addWidget(self.profile_mode_chk)

        marker_group = QtWidgets.QGroupBox("Marker style")
        marker_layout = QtWidgets.QGridLayout(marker_group)
        marker_layout.setContentsMargins(6, 6, 6, 6)
        marker_layout.setHorizontalSpacing(6)
        marker_layout.setVerticalSpacing(4)
        self.annotate_marker_shape_combo = QtWidgets.QComboBox(marker_group)
        self.annotate_marker_shape_combo.addItem("Circle", "o")
        self.annotate_marker_shape_combo.addItem("Square", "s")
        self.annotate_marker_shape_combo.addItem("Triangle", "^")
        self.annotate_marker_shape_combo.addItem("Diamond", "D")
        self.annotate_marker_shape_combo.addItem("Cross", "x")
        self.annotate_marker_shape_combo.addItem("Plus", "P")
        self.annotate_marker_shape_combo.setToolTip(
            "Choose marker shape for rendered annotation points."
        )
        shape_idx = self.annotate_marker_shape_combo.findData(
            str(getattr(self, "marker_shape", "o"))
        )
        self.annotate_marker_shape_combo.setCurrentIndex(shape_idx if shape_idx >= 0 else 0)

        self.annotate_marker_size_spin = QtWidgets.QSpinBox(marker_group)
        self.annotate_marker_size_spin.setRange(1, 100)
        self.annotate_marker_size_spin.setValue(int(getattr(self, "marker_size", 40)))
        self.annotate_marker_size_spin.setToolTip(
            "Set marker size used for annotation overlays."
        )

        marker_layout.addWidget(QtWidgets.QLabel("Shape"), 0, 0)
        marker_layout.addWidget(self.annotate_marker_shape_combo, 0, 1)
        marker_layout.addWidget(QtWidgets.QLabel("Size"), 1, 0)
        marker_layout.addWidget(self.annotate_marker_size_spin, 1, 1)
        tool_layout.addWidget(marker_group)
        
        layout.addWidget(tool_group)

        vis_group = QtWidgets.QGroupBox("6. Annotation overlays")
        vis_layout = QtWidgets.QVBoxLayout(vis_group)
        vis_layout.setContentsMargins(8, 8, 8, 8)
        vis_layout.setSpacing(6)
        vis_help_lbl = QtWidgets.QLabel("Overlay visibility")
        vis_help_lbl.setWordWrap(True)
        vis_help_lbl.setStyleSheet("color: #546e7a;")
        vis_layout.addWidget(vis_help_lbl)
        self.show_ann_master_chk = QtWidgets.QCheckBox("Show annotations")
        self.show_ann_master_chk.setChecked(True)
        row = QtWidgets.QVBoxLayout()
        row.setContentsMargins(0, 0, 0, 0)
        row.setSpacing(4)
        self._annotation_view_rows_layout = row
        self._annotation_view_checkboxes = {}
        view_specs = [
            ("frame", "Frame"),
            ("mean", "Mean Projection"),
            ("support", "Modality 2"),
            ("std", "Std Projection"),
        ]
        for key, label in view_specs:
            chk = QtWidgets.QCheckBox(label)
            act = getattr(self, "panel_actions", {}).get(key)
            chk.setChecked(bool(act.isChecked()) if act is not None else True)
            chk.toggled.connect(lambda checked, k=key: self._on_panel_toggle(k, bool(checked)))
            row.addWidget(chk)
            self._annotation_view_checkboxes[key] = chk
        self.show_frame_chk = self._annotation_view_checkboxes.get("frame")
        self.show_mean_chk = self._annotation_view_checkboxes.get("mean")
        self.show_support_chk = self._annotation_view_checkboxes.get("support")
        vis_layout.addWidget(self.show_ann_master_chk)
        vis_layout.addLayout(row)
        layout.addWidget(vis_group)

        layout.addStretch(1)
        self._refresh_annotation_view_controls()
        return panel
