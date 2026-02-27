"""Metadata editor dialog for single annotation.

Dialog for editing all metadata fields of a single annotation with
proper widget selection based on field type.
"""

from __future__ import annotations

from typing import Any, Dict, Optional

from matplotlib.backends.qt_compat import QtCore, QtGui, QtWidgets

from phage_annotator.annotation.label_taxonomy import LabelTaxonomy
from phage_annotator.annotation.metadata_schema import (
    AnnotationMetadataSchema,
    FieldType,
    get_global_schema,
)
from phage_annotator.annotation.metadata_validator import MetadataValidator
from phage_annotator.core.annotation import Keypoint


class MetadataEditorDialog(QtWidgets.QDialog):
    """Dialog for editing annotation metadata.
    
    Provides field-specific widgets for each metadata field based on
    FieldType (text input, spinbox, checkbox, combo, date picker, etc).
    """
    
    def __init__(
        self,
        annotation: Keypoint,
        taxonomy: Optional[LabelTaxonomy] = None,
        schema: Optional[AnnotationMetadataSchema] = None,
        parent: Optional[QtWidgets.QWidget] = None,
    ):
        """Initialize metadata editor dialog.
        
        Parameters
        ----------
        annotation : Keypoint
            Annotation to edit.
        taxonomy : LabelTaxonomy, optional
            Label taxonomy for label validation.
        schema : AnnotationMetadataSchema, optional
            Metadata schema (uses global if not provided).
        parent : QWidget, optional
            Parent widget.
        """
        super().__init__(parent)
        self.setWindowTitle(f"Edit Metadata: {annotation.annotation_id}")
        self.setMinimumWidth(500)
        
        self.annotation = annotation
        self.taxonomy = taxonomy
        self.schema = schema or get_global_schema()
        self.validator = MetadataValidator(self.schema)
        
        self.original_data = annotation.meta.copy()
        self.field_widgets: Dict[str, QtWidgets.QWidget] = {}
        
        self._setup_ui()
    
    def _setup_ui(self) -> None:
        """Setup dialog UI with metadata field editors."""
        layout = QtWidgets.QVBoxLayout(self)
        
        # Scrollable area for many fields
        scroll = QtWidgets.QScrollArea()
        scroll.setWidgetResizable(True)
        
        form_widget = QtWidgets.QWidget()
        form_layout = QtWidgets.QFormLayout(form_widget)
        
        # Add label editor (special case)
        label_combo = QtWidgets.QComboBox()
        if self.taxonomy:
            label_combo.addItems(self.taxonomy.get_label_names())
        label_combo.setCurrentText(self.annotation.label)
        form_layout.addRow("Label:", label_combo)
        self.field_widgets["label"] = label_combo
        
        # Add metadata field editors
        for field_def in self.schema.get_all_fields():
            widget = self._create_field_widget(field_def)
            form_layout.addRow(field_def.display_name + ":", widget)
            self.field_widgets[field_def.name] = widget
        
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
    
    def _create_field_widget(
        self,
        field_def: Any,  # FieldDefinition
    ) -> QtWidgets.QWidget:
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
        current_value = self.annotation.meta.get(field_def.name, "")
        
        if field_def.field_type == FieldType.STRING:
            widget = QtWidgets.QLineEdit()
            if isinstance(current_value, str):
                widget.setText(current_value)
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
            if isinstance(current_value, (int, float)):
                widget.setValue(int(current_value))
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
            if isinstance(current_value, (int, float)):
                widget.setValue(float(current_value))
            return widget
        
        elif field_def.field_type == FieldType.CONFIDENCE:
            # CONFIDENCE is 0-1 float
            widget = QtWidgets.QDoubleSpinBox()
            widget.setMinimum(0.0)
            widget.setMaximum(1.0)
            widget.setDecimals(3)
            widget.setSingleStep(0.05)
            if isinstance(current_value, (int, float)):
                widget.setValue(float(current_value))
            return widget
        
        elif field_def.field_type == FieldType.BOOL:
            widget = QtWidgets.QCheckBox()
            if isinstance(current_value, bool):
                widget.setChecked(current_value)
            elif isinstance(current_value, str):
                widget.setChecked(current_value.lower() in ("true", "1", "yes"))
            return widget
        
        elif field_def.field_type == FieldType.CHOICE:
            widget = QtWidgets.QComboBox()
            if field_def.constraint and field_def.constraint.allowed_values:
                widget.addItems(
                    [str(v) for v in field_def.constraint.allowed_values]
                )
            if isinstance(current_value, str):
                widget.setCurrentText(current_value)
            return widget
        
        elif field_def.field_type == FieldType.DATETIME:
            widget = QtWidgets.QDateTimeEdit()
            widget.setCalendarPopup(True)
            if isinstance(current_value, str):
                # Try to parse ISO 8601
                try:
                    dt = QtCore.QDateTime.fromString(
                        current_value, QtCore.Qt.ISODate
                    )
                    if dt.isValid():
                        widget.setDateTime(dt)
                except Exception:
                    pass
            return widget
        
        else:
            # Fallback: text edit
            widget = QtWidgets.QLineEdit()
            widget.setText(str(current_value))
            return widget
    
    def get_metadata(self) -> Dict[str, Any]:
        """Get edited metadata.
        
        Returns
        -------
        dict
            Updated metadata dictionary.
        """
        metadata = self.annotation.meta.copy()
        
        for field_def in self.schema.get_all_fields():
            widget = self.field_widgets.get(field_def.name)
            if widget is None:
                continue
            
            value = self._get_widget_value(widget, field_def.field_type)
            if value is not None:
                metadata[field_def.name] = value
        
        return metadata
    
    def accept(self) -> None:
        """Validate and accept dialog."""
        try:
            metadata = self.get_metadata()
            
            # Validate before accepting
            validated, errors = self.validator.validate_metadata(metadata)
            
            if errors:
                error_msg = "\n".join(
                    f"  {err.field_name}: {err.reason}" for err in errors
                )
                QtWidgets.QMessageBox.warning(
                    self,
                    "Validation Error",
                    f"Metadata contains errors:\n{error_msg}",
                )
                return
            
            # Update annotation
            self.annotation.meta = validated
            
            # Update label if changed
            label_widget = self.field_widgets.get("label")
            if label_widget:
                self.annotation.label = label_widget.currentText()
            
            super().accept()
        
        except Exception as e:
            QtWidgets.QMessageBox.critical(
                self, "Error", f"Error saving metadata: {e}"
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
