"""Workspace-section builders used by the main UI setup mixin."""

from __future__ import annotations

from matplotlib.backends.qt_compat import QtCore, QtWidgets

from phage_annotator.ui_qt.models.lazy_loader import (
    LAZY_LOADER_TREE_HEADER,
    LAZY_TABLE_HEADERS,
    LAZY_TABLE_HEADER_TOOLTIPS,
)


def build_modality_loader_section(owner, explore_layout: QtWidgets.QVBoxLayout) -> None:
    """Build the modality/lazy-loader group used by the Explore page."""
    sources_group = QtWidgets.QGroupBox("Loaded Files / Folders")
    sources_layout = QtWidgets.QVBoxLayout(sources_group)
    sources_layout.setContentsMargins(6, 6, 6, 6)
    sources_layout.setSpacing(6)
    owner.lazy_loader_tree = QtWidgets.QTreeWidget()
    owner.lazy_loader_tree.setColumnCount(1)
    owner.lazy_loader_tree.setHeaderLabels([LAZY_LOADER_TREE_HEADER])
    owner.lazy_loader_tree.setSelectionMode(QtWidgets.QAbstractItemView.SelectionMode.SingleSelection)
    owner.lazy_loader_tree.setUniformRowHeights(True)
    owner.lazy_loader_tree.header().setStretchLastSection(True)
    sources_layout.addWidget(owner.lazy_loader_tree)
    source_controls_row = QtWidgets.QHBoxLayout()
    owner.lazy_open_btn = QtWidgets.QPushButton("Open")
    owner.lazy_clear_btn = QtWidgets.QPushButton("Clear")
    owner.lazy_clear_btn.setToolTip("Clear previous loaded sources and reset the loader safely.")
    source_controls_row.addWidget(owner.lazy_open_btn)
    source_controls_row.addWidget(owner.lazy_clear_btn)
    source_controls_row.addStretch(1)
    sources_layout.addLayout(source_controls_row)
    explore_layout.addWidget(sources_group)

    modality_group = QtWidgets.QGroupBox("Modalities / Views")
    modality_layout = QtWidgets.QVBoxLayout(modality_group)
    modality_layout.setContentsMargins(6, 6, 6, 6)
    modality_layout.setSpacing(6)
    owner.lazy_modality_table = QtWidgets.QTableWidget(0, len(LAZY_TABLE_HEADERS))
    owner.lazy_modality_table.setHorizontalHeaderLabels(list(LAZY_TABLE_HEADERS))
    model = owner.lazy_modality_table.model()
    for column, tooltip in LAZY_TABLE_HEADER_TOOLTIPS.items():
        model.setHeaderData(
            int(column),
            QtCore.Qt.Orientation.Horizontal,
            str(tooltip),
            QtCore.Qt.ItemDataRole.ToolTipRole,
        )
    owner.lazy_modality_table.verticalHeader().setVisible(False)
    owner.lazy_modality_table.horizontalHeader().setStretchLastSection(False)
    owner.lazy_modality_table.setSelectionBehavior(QtWidgets.QAbstractItemView.SelectionBehavior.SelectRows)
    owner.lazy_modality_table.setAlternatingRowColors(True)
    owner.lazy_modality_table.setWordWrap(False)
    owner.lazy_modality_table.setHorizontalScrollMode(QtWidgets.QAbstractItemView.ScrollMode.ScrollPerPixel)
    owner.lazy_modality_table.setEditTriggers(
        QtWidgets.QAbstractItemView.EditTrigger.AllEditTriggers
    )
    modality_layout.addWidget(owner.lazy_modality_table)
    controls_row = QtWidgets.QHBoxLayout()
    owner.lazy_add_raw_btn = QtWidgets.QPushButton("Add View")
    owner.lazy_add_mean_btn = None
    owner.lazy_add_std_btn = None
    owner.lazy_remove_btn = QtWidgets.QPushButton("Remove")
    owner.lazy_remove_btn.setToolTip("Remove the selected modality/view row.")
    owner.lazy_auto_update_chk = QtWidgets.QCheckBox("Auto Update")
    owner.lazy_auto_update_chk.setChecked(True)
    owner.lazy_auto_update_chk.setVisible(True)
    owner.lazy_apply_btn = QtWidgets.QPushButton("Update Canvas")
    owner.lazy_apply_btn.setEnabled(True)
    owner.lazy_apply_btn.setVisible(True)
    controls_row.addWidget(owner.lazy_add_raw_btn)
    controls_row.addWidget(owner.lazy_remove_btn)
    controls_row.addWidget(owner.lazy_auto_update_chk)
    controls_row.addWidget(owner.lazy_apply_btn)
    controls_row.addStretch(1)
    modality_layout.addLayout(controls_row)
    explore_layout.addWidget(modality_group)
