"""Annotation table model with filtering and sorting support.

Provides a Qt table model for displaying and editing annotation metadata.
Supports real-time filtering, sorting, and column selection.
"""

from __future__ import annotations

from typing import Any, List, Optional

from matplotlib.backends.qt_compat import QtCore, QtGui, QtWidgets

from phage_annotator.annotation.label_taxonomy import LabelTaxonomy
from phage_annotator.annotation.metadata_schema import get_global_schema
from phage_annotator.core.annotation import Keypoint


class AnnotationTableModel(QtCore.QAbstractTableModel):
    """Qt table model for annotation data with filtering/sorting.
    
    Displays annotations with their metadata fields and label.
    Supports filtering by metadata values, label, and text search.
    """
    
    # Signals
    metadata_changed = QtCore.pyqtSignal(str, str, Any)  # annotation_id, field, value
    label_changed = QtCore.pyqtSignal(str, str)  # annotation_id, new_label
    
    # Standard columns for all rows
    STANDARD_COLUMNS = [
        "Label",
        "T",
        "Z",
        "X",
        "Y",
    ]
    
    def __init__(
        self,
        annotations: Optional[List[Keypoint]] = None,
        taxonomy: Optional[LabelTaxonomy] = None,
        parent: Optional[QtWidgets.QWidget] = None,
    ):
        """Initialize annotation table model.
        
        Parameters
        ----------
        annotations : List[Keypoint], optional
            Initial annotations to display.
        taxonomy : LabelTaxonomy, optional
            Label taxonomy for label validation/normalization.
        parent : QWidget, optional
            Parent widget.
        """
        super().__init__(parent)
        
        self.annotations: List[Keypoint] = annotations or []
        self.taxonomy = taxonomy
        self.schema = get_global_schema()
        
        # Filtered view (for search/filter)
        self.filtered_indices: List[int] = list(range(len(self.annotations)))
        
        # Filter state
        self._search_text = ""
        self._filters: dict[str, Any] = {}  # field -> value/range
        self._visible_columns: List[str] = list(self.STANDARD_COLUMNS)
        
        # Add baseline metadata columns
        self._visible_columns.extend(["Confidence", "Annotator", "Uncertain"])
    
    def set_annotations(self, annotations: List[Keypoint]) -> None:
        """Update annotations data.
        
        Parameters
        ----------
        annotations : List[Keypoint]
            New annotations list.
        """
        self.beginResetModel()
        self.annotations = annotations
        self.filtered_indices = list(range(len(self.annotations)))
        self.endResetModel()
    
    def rowCount(self, parent: QtCore.QModelIndex = None) -> int:
        """Get number of rows (filtered annotations)."""
        if parent and parent.isValid():
            return 0
        return len(self.filtered_indices)
    
    def columnCount(self, parent: QtCore.QModelIndex = None) -> int:
        """Get number of columns."""
        if parent and parent.isValid():
            return 0
        return len(self._visible_columns)
    
    def data(
        self,
        index: QtCore.QModelIndex,
        role: int = QtCore.Qt.DisplayRole,
    ) -> Any:
        """Get data for table cell."""
        if not index.isValid():
            return None
        
        row = index.row()
        col = index.column()
        
        if row >= len(self.filtered_indices):
            return None
        
        annotation = self.annotations[self.filtered_indices[row]]
        column_name = self._visible_columns[col]
        
        if role == QtCore.Qt.DisplayRole or role == QtCore.Qt.EditRole:
            return self._get_cell_value(annotation, column_name)
        
        elif role == QtCore.Qt.BackgroundRole:
            # Color code rows by label
            if self.taxonomy:
                label_def = self.taxonomy.get_label(annotation.label)
                if label_def:
                    return QtGui.QColor(label_def.color)
            return None
        
        elif role == QtCore.Qt.TextAlignmentRole:
            # Right-align numeric columns
            if column_name in ("T", "Z", "X", "Y"):
                return QtCore.Qt.AlignRight | QtCore.Qt.AlignVCenter
            return QtCore.Qt.AlignLeft | QtCore.Qt.AlignVCenter
        
        return None
    
    def setData(
        self,
        index: QtCore.QModelIndex,
        value: Any,
        role: int = QtCore.Qt.EditRole,
    ) -> bool:
        """Set data for table cell."""
        if not index.isValid() or role != QtCore.Qt.EditRole:
            return False
        
        row = index.row()
        col = index.column()
        
        if row >= len(self.filtered_indices):
            return False
        
        annotation = self.annotations[self.filtered_indices[row]]
        column_name = self._visible_columns[col]
        
        # Handle data updates
        if column_name == "Label":
            annotation.label = str(value)
            self.label_changed.emit(annotation.annotation_id, str(value))
        elif column_name in self.STANDARD_COLUMNS:
            # Don't allow editing coordinate columns
            return False
        else:
            # Metadata field
            annotation.meta[column_name] = value
            self.metadata_changed.emit(annotation.annotation_id, column_name, value)
        
        self.dataChanged.emit(index, index)
        return True
    
    def headerData(
        self,
        section: int,
        orientation: QtCore.Qt.Orientation,
        role: int = QtCore.Qt.DisplayRole,
    ) -> Any:
        """Get header text."""
        if role != QtCore.Qt.DisplayRole:
            return None
        
        if orientation == QtCore.Qt.Horizontal:
            if section < len(self._visible_columns):
                return self._visible_columns[section]
        
        return None
    
    def flags(self, index: QtCore.QModelIndex) -> QtCore.Qt.ItemFlags:
        """Get item flags (editable/selectable)."""
        if not index.isValid():
            return QtCore.Qt.NoItemFlags
        
        flags = super().flags(index)
        
        # Disable editing for coordinate columns
        column_name = self._visible_columns[index.column()]
        if column_name not in ("T", "Z", "X", "Y"):
            flags |= QtCore.Qt.ItemIsEditable
        
        return flags
    
    def set_column_visibility(self, columns: List[str]) -> None:
        """Set which columns to display.
        
        Parameters
        ----------
        columns : List[str]
            List of column names to display.
        """
        self.beginResetModel()
        self._visible_columns = columns
        self.endResetModel()
    
    def add_metadata_column(self, column_name: str) -> None:
        """Add a metadata column to display.
        
        Parameters
        ----------
        column_name : str
            Metadata field name.
        """
        if column_name not in self._visible_columns:
            self.beginInsertColumns(
                QtCore.QModelIndex(),
                len(self._visible_columns),
                len(self._visible_columns),
            )
            self._visible_columns.append(column_name)
            self.endInsertColumns()
    
    def remove_metadata_column(self, column_name: str) -> None:
        """Remove a metadata column from display.
        
        Parameters
        ----------
        column_name : str
            Metadata field name.
        """
        if column_name in self._visible_columns:
            index = self._visible_columns.index(column_name)
            self.beginRemoveColumns(QtCore.QModelIndex(), index, index)
            self._visible_columns.pop(index)
            self.endRemoveColumns()
    
    def set_search_text(self, text: str) -> None:
        """Set search/filter text.
        
        Parameters
        ----------
        text : str
            Search text (matched against label, coordinates, and text fields).
        """
        self._search_text = text.lower()
        self._rebuild_filtered_indices()
    
    def set_field_filter(self, field_name: str, value: Any) -> None:
        """Set filter for a specific field.
        
        Parameters
        ----------
        field_name : str
            Metadata field name.
        value : Any
            Filter value (exact match or range for numeric).
        """
        if value is None:
            self._filters.pop(field_name, None)
        else:
            self._filters[field_name] = value
        self._rebuild_filtered_indices()
    
    def _rebuild_filtered_indices(self) -> None:
        """Rebuild filtered annotation indices based on current filters."""
        self.beginResetModel()
        
        self.filtered_indices = []
        for i, annotation in enumerate(self.annotations):
            # Apply search text filter
            if self._search_text:
                search_text = self._search_text
                if not (
                    search_text in annotation.label.lower()
                    or search_text in str(annotation.x).lower()
                    or search_text in str(annotation.y).lower()
                ):
                    continue
            
            # Apply field filters
            if not self._passes_field_filters(annotation):
                continue
            
            self.filtered_indices.append(i)
        
        self.endResetModel()
    
    def _passes_field_filters(self, annotation: Keypoint) -> bool:
        """Check if annotation passes all field filters."""
        for field_name, filter_value in self._filters.items():
            annotation_value = annotation.meta.get(field_name)
            
            if annotation_value != filter_value:
                return False
        
        return True
    
    def _get_cell_value(self, annotation: Keypoint, column_name: str) -> Any:
        """Get value for a cell."""
        if column_name == "Label":
            return annotation.label
        elif column_name == "T":
            return annotation.t
        elif column_name == "Z":
            return annotation.z
        elif column_name == "X":
            return f"{annotation.x:.1f}"
        elif column_name == "Y":
            return f"{annotation.y:.1f}"
        else:
            # Metadata field
            return annotation.meta.get(column_name, "")
    
    def get_annotation(self, row: int) -> Optional[Keypoint]:
        """Get annotation at row.
        
        Parameters
        ----------
        row : int
            Row index (in filtered view).
        
        Returns
        -------
        Keypoint or None
            Annotation at row, or None if out of range.
        """
        if 0 <= row < len(self.filtered_indices):
            return self.annotations[self.filtered_indices[row]]
        return None
