"""Extracted method group 17 for UiExtrasMixin."""

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



class LazyAnnotationTableMixin:
    """Method group 17 extracted from UiExtrasMixin."""

    def _insert_lazy_table_row(self, table, row_spec: LazyTableRowSpec) -> None:
        """Insert one derived row into the lazy-loading table."""
        source_images = list(self._lazy_loader_source_images())
        projection_options = ("raw", "mean", "median", "std", "min", "max")
        projection_labels = {
            "raw": "Source Frame",
            "mean": "Mean",
            "median": "Median",
            "std": "Std",
            "min": "Min",
            "max": "Max",
        }
        row = table.rowCount()
        table.insertRow(row)
        visible_widget = self._centered_lazy_checkbox(
            table,
            checked=row_spec.visible,
            tooltip="Show or hide this panel on the canvas.",
            on_toggled=lambda checked, k=row_spec.panel_key: self._on_panel_toggle(str(k), bool(checked)),
        )
        table.setCellWidget(row, LAZY_TABLE_COLUMN_SHOW, visible_widget)
        points_widget = self._centered_lazy_checkbox(
            table,
            checked=row_spec.show_points,
            tooltip="Show annotation points on this panel.",
            on_toggled=lambda checked, k=row_spec.panel_key: self._on_annotation_panel_toggle(str(k), bool(checked)),
        )
        table.setCellWidget(row, LAZY_TABLE_COLUMN_POINTS, points_widget)

        table_btn = QtWidgets.QToolButton(table)
        table_btn.setText("Open")
        table_btn.setToolButtonStyle(QtCore.Qt.ToolButtonStyle.ToolButtonTextOnly)
        table_btn.setToolTip("Open the annotation table focused on this panel row.")
        table_btn.clicked.connect(
            lambda _checked=False, k=row_spec.panel_key: self._open_annotation_table_for_panel(str(k))
        )
        table.setCellWidget(row, LAZY_TABLE_COLUMN_TABLE, table_btn)

        name_item = QtWidgets.QTableWidgetItem(str(row_spec.panel_name))
        name_item.setData(QtCore.Qt.ItemDataRole.UserRole, row_spec.role_key)
        binding_txt = str(row_spec.annotation_binding_path or "Unbound")
        mode_map = {
            "shared_source": "Shared with source",
            "independent": "Independent",
            "read_only": "Read-only overlay",
        }
        mode_txt = str(mode_map.get(str(row_spec.annotation_mode), str(row_spec.annotation_mode).title()))
        name_item.setToolTip(
            f"Annotation mode: {mode_txt}\n"
            f"Writable: {'yes' if row_spec.annotation_writable else 'no'}\n"
            f"Context: {row_spec.annotation_context_key or 'unresolved'}\n"
            f"Binding: {binding_txt}"
        )
        name_item.setFlags(name_item.flags() | QtCore.Qt.ItemFlag.ItemIsEditable)
        table.setItem(row, LAZY_TABLE_COLUMN_NAME, name_item)

        source_combo = QtWidgets.QComboBox(table)
        for img in source_images:
            source_combo.addItem(str(getattr(img, "name", f"Image {img.id}")), int(img.id))
        src_idx = max(0, source_combo.findData(int(row_spec.source_image_id)))
        source_combo.setCurrentIndex(src_idx)

        def _combo_image_id(combo: QtWidgets.QComboBox, fallback: int) -> int:
            """Handle the combo image id helper flow."""
            value = combo.currentData()
            try:
                return int(value)
            except Exception:
                return int(fallback)

        if str(row_spec.role_key) == "builtin:support":
            source_combo.currentIndexChanged.connect(
                lambda _i, combo=source_combo, fallback=row_spec.source_image_id: self._on_lazy_builtin_support_source_changed(
                    _combo_image_id(combo, int(fallback))
                )
            )
        elif isinstance(row_spec.role_key, str) and str(row_spec.role_key).startswith("builtin:"):
            panel_key = str(row_spec.role_key).split(":", 1)[1]
            source_combo.currentIndexChanged.connect(
                lambda _i, k=panel_key, combo=source_combo, fallback=row_spec.source_image_id: self._on_lazy_builtin_source_changed(
                    str(k), _combo_image_id(combo, int(fallback))
                )
            )
        else:
            source_combo.currentIndexChanged.connect(
                lambda _i, mid=int(row_spec.role_key), combo=source_combo, fallback=row_spec.source_image_id: self._on_lazy_modality_source_changed(
                    mid, _combo_image_id(combo, int(fallback))
                )
            )
        table.setCellWidget(row, LAZY_TABLE_COLUMN_SOURCE, source_combo)

        view_combo = QtWidgets.QComboBox(table)
        for projection in projection_options:
            view_combo.addItem(str(projection_labels.get(projection, projection.title())), projection)
        proj_idx = max(0, view_combo.findData(str(row_spec.projection_key).strip().lower()))
        view_combo.setCurrentIndex(proj_idx)
        view_combo.setEnabled(bool(row_spec.projection_editable))
        if isinstance(row_spec.role_key, str) and str(row_spec.role_key).startswith("builtin:"):
            panel_key = str(row_spec.role_key).split(":", 1)[1]
            view_combo.currentIndexChanged.connect(
                lambda _i, k=panel_key, combo=view_combo: self._on_lazy_builtin_projection_changed(
                    str(k), str(combo.currentData())
                )
            )
        else:
            view_combo.currentIndexChanged.connect(
                lambda _i, mid=int(row_spec.role_key), combo=view_combo: self._on_lazy_modality_projection_changed(
                    mid, str(combo.currentData())
                )
            )
        table.setCellWidget(row, LAZY_TABLE_COLUMN_PROJECTION, view_combo)

        owner_combo = QtWidgets.QComboBox(table)
        owner_combo.addItem("Independent", "independent")
        owner_combo.addItem("Shared", "shared_source")
        owner_combo.addItem("Read-only", "read_only")
        owner_idx = max(0, owner_combo.findData(str(row_spec.annotation_mode or "independent")))
        owner_combo.setCurrentIndex(owner_idx)
        owner_combo.setToolTip(
            "Choose whether this row owns its annotations, shares the source context, or is read-only."
        )
        owner_combo.currentIndexChanged.connect(
            lambda _i, k=row_spec.panel_key, combo=owner_combo: self._set_lazy_annotation_context_mode_for_panel(
                str(k),
                str(combo.currentData()),
            )
        )
        table.setCellWidget(row, LAZY_TABLE_COLUMN_ANNOTATION_MODE, owner_combo)

        binding_path = str(row_spec.annotation_binding_path or "").strip()
        binding_exists = bool(binding_path and Path(binding_path).exists())
        file_cell = QtWidgets.QWidget(table)
        file_layout = QtWidgets.QHBoxLayout(file_cell)
        file_layout.setContentsMargins(2, 0, 2, 0)
        file_layout.setSpacing(4)
        path_edit = QtWidgets.QLineEdit(file_cell)
        path_edit.setReadOnly(True)
        path_edit.setText(binding_path)
        path_edit.setPlaceholderText("No annotation file detected")
        path_edit.setToolTip(
            "Annotation file linked to this row.\n"
            f"Path: {binding_path if binding_path else 'Not bound'}\n"
            f"Status: {'Available' if binding_exists else 'Missing' if binding_path else 'Not bound'}"
        )
        browse_btn = QtWidgets.QToolButton(file_cell)
        browse_btn.setText("...")
        browse_btn.setToolTip("Browse for a different annotation file to link to this row.")
        browse_btn.clicked.connect(
            lambda _checked=False, k=row_spec.panel_key: self._bind_lazy_annotation_file_for_panel(str(k))
        )
        file_layout.addWidget(path_edit, 1)
        file_layout.addWidget(browse_btn)
        table.setCellWidget(row, LAZY_TABLE_COLUMN_ANNOTATION_FILE, file_cell)

        group_editor = QtWidgets.QLineEdit(str(row_spec.group_key), table)
        group_editor.setAlignment(QtCore.Qt.AlignmentFlag.AlignCenter)
        group_editor.setClearButtonEnabled(False)
        group_editor.setToolTip("Edit the sync group directly in this cell.")
        group_editor.editingFinished.connect(
            lambda rk=row_spec.role_key, editor=group_editor: self._commit_lazy_group_value(rk, editor.text())
        )
        table.setCellWidget(row, LAZY_TABLE_COLUMN_GROUP, group_editor)
        table.setCellWidget(
            row,
            LAZY_TABLE_COLUMN_SYNC_CONTRAST,
            self._centered_lazy_checkbox(
                table,
                checked=row_spec.sync_contrast,
                tooltip="Enable contrast sync for this row.",
                on_toggled=lambda checked, rk=row_spec.role_key: self._set_sync_mode_for_role(rk, "contrast", bool(checked)),
            ),
        )
        table.setCellWidget(
            row,
            LAZY_TABLE_COLUMN_SYNC_VIEW,
            self._centered_lazy_checkbox(
                table,
                checked=row_spec.sync_view,
                tooltip="Enable zoom/pan sync for this row.",
                on_toggled=lambda checked, rk=row_spec.role_key: self._set_sync_mode_for_role(rk, "zoom", bool(checked)),
            ),
        )
        table.setCellWidget(
            row,
            LAZY_TABLE_COLUMN_SYNC_TIME,
            self._centered_lazy_checkbox(
                table,
                checked=row_spec.sync_time,
                tooltip="Enable playback sync for this row.",
                on_toggled=lambda checked, rk=row_spec.role_key: self._set_sync_mode_for_role(rk, "playback", bool(checked)),
            ),
        )
