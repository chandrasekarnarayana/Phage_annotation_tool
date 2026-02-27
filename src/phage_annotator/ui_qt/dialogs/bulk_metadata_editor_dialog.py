"""Bulk metadata editor for multiple annotations.

Dialog for applying metadata changes to multiple annotations in batch,
with selective field application (don't overwrite unselected fields).
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from matplotlib.backends.qt_compat import QtCore, QtGui, QtWidgets

from phage_annotator.annotation.label_taxonomy import LabelTaxonomy
from phage_annotator.annotation.metadata_schema import (
    AnnotationMetadataSchema,
    FieldType,
    get_global_schema,
)
from phage_annotator.annotation.metadata_validator import MetadataValidator
from phage_annotator.core.annotation import Keypoint


class BulkMetadataEditorDialog(QtWidgets.QDialog):
    """Dialog for batch editing metadata on multiple annotations.
    
    Allows selective field updates - only fields with checkboxes checked
    will be applied to all selected annotations.
    """
    
    def __init__(
        self,
        annotations: List[Keypoint],
        taxonomy: Optional[LabelTaxonomy] = None,
        schema: Optional[AnnotationMetadataSchema] = None,
        parent: Optional[QtWidgets.QWidget] = None,
    ):
        """Initialize bulk metadata editor dialog.
        
        Parameters
        ----------
        annotations : List[Keypoint]
            Annotations to edit (batch operation).
        taxonomy : LabelTaxonomy, optional
            Label taxonomy for label validation.
        schema : AnnotationMetadataSchema, optional
            Metadata schema (uses global if not provided).
        parent : QWidget, optional
            Parent widget.
        """
        super().__init__(parent)
        self.setWindowTitle(f"Edit Metadata (Bulk): {len(annotations)} annotations")
        self.setMinimumWidth(500)
        
        self.annotations = annotations
        self.taxonomy = taxonomy
        self.schema = schema or get_global_schema()
        self.validator = MetadataValidator(self.schema)
        
        self.field_widgets: Dict[str, tuple[QtWidgets.QCheckBox, QtWidgets.QWidget]] = {}
        
        self._setup_ui()
    
    def _setup_ui(self) -> None:
        """Setup dialog UI with bulk edit controls."""
        layout = QtWidgets.QVBoxLayout(self)
        
        # Info label
        info_label = QtWidgets.QLabel(
            f"Editing {len(self.annotations)} annotations. "
            "Check fields below to apply changes:"
        )
        info_label.setWordWrap(True)
        layout.addWidget(info_label)
        
        # Scrollable area for field editors
        scroll = QtWidgets.QScrollArea()
        scroll.setWidgetResizable(True)
        
        form_widget = QtWidgets.QWidget()
        form_layout = QtWidgets.QFormLayout(form_widget)
        
        # Bulk label editor
        label_checkbox = QtWidgets.QCheckBox()
        label_combo = QtWidgets.QComboBox()
        if self.taxonomy:
            label_combo.addItems(self.taxonomy.get_label_names())
        label_combo.setEnabled(False)
        label_checkbox.toggled.connect(label_combo.setEnabled)
        
        label_widget_layout = QtWidgets.QHBoxLayout()
        label_widget_layout.addWidget(label_checkbox)
        label_widget_layout.addWidget(label_combo)
        form_layout.addRow("Label:", label_widget_layout)
        self.field_widgets["label"] = (label_checkbox, label_combo)
        
        # Bulk metadata field editors
        for field_def in self.schema.get_all_fields():
            checkbox = QtWidgets.QCheckBox()
            widget = self._create_field_widget(field_def)
            widget.setEnabled(False)
            checkbox.toggled.connect(widget.setEnabled)
            
            # Layout with checkbox and widget side-by-side
            field_layout = QtWidgets.QHBoxLayout()
            field_layout.addWidget(checkbox)
            field_layout.addWidget(widget)
            
            form_layout.addRow(field_def.display_name + ":", field_layout)
            self.field_widgets[field_def.name] = (checkbox, widget)
        
        scroll.setWidget(form_widget)
        layout.addWidget(scroll)
        
        # Dialog buttons
        button_box = QtWidgets.QDialogButtonBox(
            QtWidgets.QDialogButtonBox.Ok
            | QtWidgets.QDialogButtonBox.Cancel
        )
        button_box.accepted.connect(self.accept)
        button_box.rejected.connect(self.reject)
        layout.addWidget(button_box)
    
    def _create_field_widget(self, field_def: Any) -> QtWidgets.QWidget:
        """Create appropriate widget for field type.
        
        Parameters
        ----------
        field_def : FieldDefinition
            Field definition specifying type and constraints.
        
        Returns
        -------
        QWidget
            Appropriate Qt widget for the field.
        """
        if field_def.field_type == FieldType.STRING:
            widget = QtWidgets.QLineEdit()
            if field_def.constraint and field_def.constraint.max_length:
                widget.setMaxLength(field_def.constraint.max_length)
            return widget
        
        elif field_def.field_type == FieldType.INT:
            widget = QtWidgets.QSpinBox()
            constraint = field_def.constraint
            if constraint:
                if constraint.min_value is not None:
                    widget.setMinimum(int(constraint.min_value))
                if constraint.max_value is not None:
                    widget.setMaximum(int(constraint.max_value))
            return widget
        
        elif field_def.field_type == FieldType.FLOAT:
            widget = QtWidgets.QDoubleSpinBox()
            constraint = field_def.constraint
            if constraint:
                if constraint.min_value is not None:
                    widget.setMinimum(float(constraint.min_value))
                if constraint.max_value is not None:
                    widget.setMaximum(float(constraint.max_value))
            widget.setDecimals(3)
            return widget
        
        elif field_def.field_type == FieldType.CONFIDENCE:
            widget = QtWidgets.QDoubleSpinBox()
            widget.setMinimum(0.0)
            widget.setMaximum(1.0)
            widget.setDecimals(3)
            widget.setSingleStep(0.05)
            return widget
        
        elif field_def.field_type == FieldType.BOOL:
            widget = QtWidgets.QCheckBox()
            return widget
        
        elif field_def.field_type == FieldType.CHOICE:
            widget = QtWidgets.QComboBox()
            if field_def.constraint and field_def.constraint.allowed_values:
                widget.addItems(
                    [str(v) for v in field_def.constraint.allowed_values]
                )
            return widget
        
        elif field_def.field_type == FieldType.DATETIME:
            widget = QtWidgets.QDateTimeEdit()
            widget.setCalendarPopup(True)
            return widget
        
        else:
            return QtWidgets.QLineEdit()
    
    def get_updates(self) -> Dict[str, Any]:
        """Get selected metadata updates.
        
        Only returns fields with checkbox enabled.
        
        Returns
        -------
        dict
            Dictionary of field_name -> value for checked fields.
        """
        updates = {}
        
        # Label
        label_checkbox, label_combo = self.field_widgets.get("label", (None, None))
        if label_checkbox and label_checkbox.isChecked():
            updates["label"] = label_combo.currentText()
        
        # Metadata fields
        for field_def in self.schema.get_all_fields():
            checkbox, widget = self.field_widgets.get(
                field_def.name, (None, None)
            )
            if checkbox and checkbox.isChecked():
                value = self._get_widget_value(widget, field_def.field_type)
                if value is not None:
                    updates[field_def.name] = value
        
        return updates
    
    def accept(self) -> None:
        """Validate and accept dialog."""
        try:
            updates = self.get_updates()
            
            if not updates:
                QtWidgets.QMessageBox.information(
                    self,
                    "No Changes",
                    "Please select at least one field to update.",
                )
                return
            
            # Validate updates by checking if they work with all annotations
            for annotation in self.annotations:
                test_meta = annotation.meta.copy()
                
                # Apply updates
                for key, value in updates.items():
                    if key != "label":
                        test_meta[key] = value
                
                # Validate
                _, errors = self.validator.validate_metadata(test_meta)
                if errors:
                    error_msg = "\n".join(
                        f"  {err.field_name}: {err.reason}" for err in errors
                    )
                    QtWidgets.QMessageBox.warning(
                        self,
                        "Validation Error",
                        f"Updates contain errors:\n{error_msg}",
                    )
                    return
            
            # Apply updates to all annotations
            for annotation in self.annotations:
                for key, value in updates.items():
                    if key == "label":
                        annotation.label = value
                    else:
                        annotation.meta[key] = value
            
            super().accept()
        
        except Exception as e:
            QtWidgets.QMessageBox.critical(
                self, "Error", f"Error applying bulk updates: {e}"
            )
    
    def _get_widget_value(
        self,
        widget: QtWidgets.QWidget,
        field_type: FieldType,
    ) -> Any:
        """Get value from field widget.
        
        Parameters
        ----------
        widget : QWidget
            The field widget.
        field_type : FieldType
            Expected field type.
        
        Returns
        -------
        Any
            Extracted value.
        """
        if isinstance(widget, QtWidgets.QLineEdit):
            return widget.text()
        elif isinstance(widget, QtWidgets.QSpinBox):
            return widget.value()
        elif isinstance(widget, QtWidgets.QDoubleSpinBox):
            return widget.value()
        elif isinstance(widget, QtWidgets.QCheckBox):
            return widget.isChecked()
        elif isinstance(widget, QtWidgets.QComboBox):
            return widget.currentText()
        elif isinstance(widget, QtWidgets.QDateTimeEdit):
            return widget.dateTime().toString(QtCore.Qt.ISODate)
        
        return None
