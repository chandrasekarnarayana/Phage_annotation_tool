"""Annotation table panel widget for annotation management.

Main UI panel displaying annotation table with filtering, search,
and metadata editing capabilities.
"""

from __future__ import annotations

from typing import List, Optional

from matplotlib.backends.qt_compat import QtCore, QtGui, QtWidgets

from phage_annotator.annotation.label_taxonomy import LabelTaxonomy
from phage_annotator.annotation.metadata_schema import get_global_schema
from phage_annotator.core.annotation import Keypoint
from phage_annotator.ui_qt.dialogs.bulk_metadata_editor_dialog import (
    BulkMetadataEditorDialog,
)
from phage_annotator.ui_qt.dialogs.metadata_editor_dialog import (
    MetadataEditorDialog,
)
from phage_annotator.ui_qt.models.annotation_table_model import AnnotationTableModel


class AnnotationTablePanel(QtWidgets.QDockWidget):
    """Dock widget panel with annotation table and controls.
    
    Provides annotation browsing, filtering, and metadata editing.
    Emits signals when selections change or metadata is edited.
    """
    
    # Signals
    annotation_selected = QtCore.pyqtSignal(str)  # annotation_id
    annotations_selected = QtCore.pyqtSignal(list)  # List[str] annotation_ids
    metadata_edited = QtCore.pyqtSignal(str, str, object)  # annotation_id, field, value
    labels_changed = QtCore.pyqtSignal(dict)  # {annotation_id: new_label}
    
    def __init__(
        self,
        annotations: Optional[List[Keypoint]] = None,
        taxonomy: Optional[LabelTaxonomy] = None,
        parent: Optional[QtWidgets.QWidget] = None,
    ):
        """Initialize annotation table panel.
        
        Parameters
        ----------
        annotations : List[Keypoint], optional
            Initial annotations to display.
        taxonomy : LabelTaxonomy, optional
            Label taxonomy for validation and colors.
        parent : QWidget, optional
            Parent widget.
        """
        super().__init__("Annotations", parent)
        
        self.annotations = annotations or []
        self.taxonomy = taxonomy
        self.schema = get_global_schema()
        
        self.table_model: Optional[AnnotationTableModel] = None
        self.table_view: Optional[QtWidgets.QTableView] = None
        
        self._setup_ui()
        
        if annotations:
            self.set_annotations(annotations)
    
    def _setup_ui(self) -> None:
        """Setup panel UI with table and controls."""
        central_widget = QtWidgets.QWidget()
        layout = QtWidgets.QVBoxLayout(central_widget)
        
        # Search and filter controls
        controls_layout = QtWidgets.QHBoxLayout()
        
        # Search box
        controls_layout.addWidget(QtWidgets.QLabel("Search:"))
        self.search_input = QtWidgets.QLineEdit()
        self.search_input.setPlaceholderText("Search labels, coordinates...")
        self.search_input.textChanged.connect(self._on_search_changed)
        controls_layout.addWidget(self.search_input)
        
        # Label filter
        controls_layout.addWidget(QtWidgets.QLabel("Label:"))
        self.label_filter = QtWidgets.QComboBox()
        self.label_filter.addItem("(All)", None)
        if self.taxonomy:
            for label_name in self.taxonomy.get_label_names():
                self.label_filter.addItem(label_name, label_name)
        self.label_filter.currentTextChanged.connect(self._on_label_filter_changed)
        controls_layout.addWidget(self.label_filter)
        
        # Confidence filter
        controls_layout.addWidget(QtWidgets.QLabel("Min Confidence:"))
        self.confidence_filter = QtWidgets.QDoubleSpinBox()
        self.confidence_filter.setMinimum(0.0)
        self.confidence_filter.setMaximum(1.0)
        self.confidence_filter.setValue(0.0)
        self.confidence_filter.setSingleStep(0.1)
        self.confidence_filter.valueChanged.connect(self._on_confidence_filter_changed)
        controls_layout.addWidget(self.confidence_filter)
        
        controls_layout.addStretch()
        layout.addLayout(controls_layout)
        
        # Table view
        self.table_view = QtWidgets.QTableView()
        self.table_view.setSelectionBehavior(
            QtWidgets.QAbstractItemView.SelectRows
        )
        self.table_view.setSelectionMode(
            QtWidgets.QAbstractItemView.ExtendedSelection
        )
        self.table_view.setAlternatingRowColors(True)
        self.table_view.setColumnHidden(0, False)  # Show all columns initially
        
        # Connect table signals
        self.table_view.doubleClicked.connect(self._on_table_double_click)
        self.table_view.selectionModel().selectionChanged.connect(
            self._on_selection_changed
        )
        
        layout.addWidget(self.table_view)
        
        # Action buttons
        button_layout = QtWidgets.QHBoxLayout()
        
        self.edit_button = QtWidgets.QPushButton("Edit Selected")
        self.edit_button.clicked.connect(self._on_edit_single)
        self.edit_button.setEnabled(False)
        button_layout.addWidget(self.edit_button)
        
        self.bulk_edit_button = QtWidgets.QPushButton("Bulk Edit...")
        self.bulk_edit_button.clicked.connect(self._on_bulk_edit)
        self.bulk_edit_button.setEnabled(False)
        button_layout.addWidget(self.bulk_edit_button)
        
        self.refresh_button = QtWidgets.QPushButton("Refresh")
        self.refresh_button.clicked.connect(self._on_refresh)
        button_layout.addWidget(self.refresh_button)
        
        button_layout.addStretch()
        layout.addLayout(button_layout)
        
        self.setWidget(central_widget)
    
    def set_annotations(self, annotations: List[Keypoint]) -> None:
        """Set annotations to display.
        
        Parameters
        ----------
        annotations : List[Keypoint]
            Annotations to show in table.
        """
        self.annotations = annotations
        
        # Create or update model
        if self.table_model is None:
            self.table_model = AnnotationTableModel(
                annotations,
                taxonomy=self.taxonomy,
                parent=self,
            )
            self.table_view.setModel(self.table_model)
            
            # Connect model signals
            self.table_model.metadata_changed.connect(
                self._on_model_metadata_changed
            )
            self.table_model.label_changed.connect(self._on_model_label_changed)
            
            # Adjust column widths
            self.table_view.resizeColumnsToContents()
        else:
            self.table_model.set_annotations(annotations)
    
    def _on_search_changed(self, text: str) -> None:
        """Handle search text change."""
        if self.table_model:
            self.table_model.set_search_text(text)
    
    def _on_label_filter_changed(self, text: str) -> None:
        """Handle label filter change."""
        if self.table_model:
            label = self.label_filter.currentData()
            if label:
                self.table_model.set_field_filter("label", label)
            else:
                self.table_model.set_field_filter("label", None)
    
    def _on_confidence_filter_changed(self, value: float) -> None:
        """Handle confidence filter change."""
        if self.table_model and value > 0.0:
            self.table_model.set_field_filter("confidence", value)
        elif self.table_model:
            self.table_model.set_field_filter("confidence", None)
    
    def _on_table_double_click(self, index: QtCore.QModelIndex) -> None:
        """Handle double-click to edit annotation."""
        if self.table_model and index.isValid():
            annotation = self.table_model.get_annotation(index.row())
            if annotation:
                self._show_edit_dialog(annotation)
    
    def _on_selection_changed(self) -> None:
        """Handle table selection change."""
        if not self.table_view:
            return
        
        selected_indices = self.table_view.selectionModel().selectedRows()
        
        # Get selected annotations
        selected_annotations = []
        for model_index in selected_indices:
            if self.table_model:
                ann = self.table_model.get_annotation(model_index.row())
                if ann:
                    selected_annotations.append(ann.annotation_id)
        
        # Emit signals
        if selected_annotations:
            self.annotations_selected.emit(selected_annotations)
            
            # Single selection
            if len(selected_annotations) == 1:
                self.annotation_selected.emit(selected_annotations[0])
        
        # Enable/disable buttons
        self.edit_button.setEnabled(len(selected_annotations) == 1)
        self.bulk_edit_button.setEnabled(len(selected_annotations) > 0)
    
    def _on_edit_single(self) -> None:
        """Handle edit button click."""
        selected_indices = self.table_view.selectionModel().selectedRows()
        if selected_indices and self.table_model:
            annotation = self.table_model.get_annotation(selected_indices[0].row())
            if annotation:
                self._show_edit_dialog(annotation)
    
    def _show_edit_dialog(self, annotation: Keypoint) -> None:
        """Show single-edit dialog.
        
        Parameters
        ----------
        annotation : Keypoint
            Annotation to edit.
        """
        dialog = MetadataEditorDialog(
            annotation,
            taxonomy=self.taxonomy,
            schema=self.schema,
            parent=self,
        )
        
        if dialog.exec() == QtWidgets.QDialog.Accepted:
            # Emit signals for changed fields
            for field_name, new_value in annotation.meta.items():
                self.metadata_edited.emit(
                    annotation.annotation_id, field_name, new_value
                )
            
            # Refresh table
            self.table_view.viewport().update()
    
    def _on_bulk_edit(self) -> None:
        """Handle bulk edit button click."""
        # Get selected annotations
        selected_indices = self.table_view.selectionModel().selectedRows()
        selected_annotations = []
        
        for model_index in selected_indices:
            if self.table_model:
                ann = self.table_model.get_annotation(model_index.row())
                if ann:
                    selected_annotations.append(ann)
        
        if not selected_annotations:
            return
        
        # Show bulk edit dialog
        dialog = BulkMetadataEditorDialog(
            selected_annotations,
            taxonomy=self.taxonomy,
            schema=self.schema,
            parent=self,
        )
        
        if dialog.exec() == QtWidgets.QDialog.Accepted:
            # Update with changes
            label_changes = {}
            for annotation in selected_annotations:
                if annotation.label not in label_changes.values():
                    label_changes[annotation.annotation_id] = annotation.label
            
            self.labels_changed.emit(label_changes)
            self.table_view.viewport().update()
    
    def _on_model_metadata_changed(
        self,
        annotation_id: str,
        field: str,
        value: object,
    ) -> None:
        """Handle metadata change from model."""
        self.metadata_edited.emit(annotation_id, field, value)
    
    def _on_model_label_changed(self, annotation_id: str, new_label: str) -> None:
        """Handle label change from model."""
        self.labels_changed.emit({annotation_id: new_label})
    
    def _on_refresh(self) -> None:
        """Handle refresh button."""
        if self.table_model:
            self.table_model.set_annotations(self.annotations)
