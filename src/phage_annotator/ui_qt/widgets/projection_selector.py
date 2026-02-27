"""Projection selector widget for choosing projection type and axis.

Allows users to select:
- Projection type (Raw, Mean, Std, Min, Max)
- Projection axis (T for time, Z for depth)
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Optional

from PyQt5 import QtCore, QtWidgets

if TYPE_CHECKING:
    from phage_annotator.session.modality import ModalitySpec, ProjectionType


class ProjectionSelectorWidget(QtWidgets.QWidget):
    """Widget for selecting projection type and axis.
    
    Emits:
        projection_changed: (projection_type, projection_axis) tuple
    """
    
    projection_changed = QtCore.pyqtSignal(str, str)  # projection_type, projection_axis
    
    def __init__(self, parent: Optional[QtWidgets.QWidget] = None):
        """Initialize projection selector.
        
        Parameters
        ----------
        parent : QWidget, optional
            Parent widget.
        """
        super().__init__(parent)
        self._setup_ui()
        self._current_modality_idx: Optional[int] = None
    
    def _setup_ui(self) -> None:
        """Set up the UI layout."""
        layout = QtWidgets.QGridLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        
        # Projection type label and combo
        layout.addWidget(QtWidgets.QLabel("Projection:"), 0, 0)
        self.projection_combo = QtWidgets.QComboBox()
        self.projection_combo.addItems([
            "Raw",
            "Mean",
            "Std Dev",
            "Min",
            "Max",
        ])
        self.projection_combo.currentTextChanged.connect(self._on_projection_changed)
        layout.addWidget(self.projection_combo, 0, 1)
        
        # Projection axis label and combo
        layout.addWidget(QtWidgets.QLabel("Axis:"), 1, 0)
        self.axis_combo = QtWidgets.QComboBox()
        self.axis_combo.addItems([
            "T (Time)",
            "Z (Depth)",
        ])
        self.axis_combo.currentTextChanged.connect(self._on_axis_changed)
        layout.addWidget(self.axis_combo, 1, 1)
        
        # Stretch at bottom to avoid tall widget
        layout.addItem(
            QtWidgets.QSpacerItem(0, 0, QtWidgets.QSizePolicy.Minimum, QtWidgets.QSizePolicy.Expanding),
            2, 0, 1, 2,
        )
        
        self.setMaximumWidth(250)
    
    def set_modality(self, modality: ModalitySpec) -> None:
        """Set the displayed modality.
        
        Parameters
        ----------
        modality : ModalitySpec
            The modality to display settings for.
        """
        self._current_modality_idx = modality.idx
        
        # Block signals to prevent emission during update
        self.projection_combo.blockSignals(True)
        self.axis_combo.blockSignals(True)
        
        # Set projection type
        projection_name = modality.projection_type.value.replace("raw", "Raw").title()
        projection_names = {
            "raw": "Raw",
            "mean": "Mean",
            "std": "Std Dev",
            "min": "Min",
            "max": "Max",
        }
        display_name = projection_names.get(modality.projection_type.value, "Raw")
        idx = self.projection_combo.findText(display_name)
        if idx >= 0:
            self.projection_combo.setCurrentIndex(idx)
        
        # Set axis
        axis_text = "T (Time)" if modality.display_settings.projection_axis == "t" else "Z (Depth)"
        idx = self.axis_combo.findText(axis_text)
        if idx >= 0:
            self.axis_combo.setCurrentIndex(idx)
        
        self.projection_combo.blockSignals(False)
        self.axis_combo.blockSignals(False)
    
    def _on_projection_changed(self, text: str) -> None:
        """Handle projection type change."""
        projection_map = {
            "Raw": "raw",
            "Mean": "mean",
            "Std Dev": "std",
            "Min": "min",
            "Max": "max",
        }
        projection_type = projection_map.get(text, "raw")
        
        # Get current axis
        axis_text = self.axis_combo.currentText()
        projection_axis = "t" if "Time" in axis_text else "z"
        
        self.projection_changed.emit(projection_type, projection_axis)
    
    def _on_axis_changed(self, text: str) -> None:
        """Handle projection axis change."""
        projection_axis = "t" if "Time" in text else "z"
        
        # Get current projection type
        projection_map = {
            "Raw": "raw",
            "Mean": "mean",
            "Std Dev": "std",
            "Min": "min",
            "Max": "max",
        }
        projection_text = self.projection_combo.currentText()
        projection_type = projection_map.get(projection_text, "raw")
        
        self.projection_changed.emit(projection_type, projection_axis)
    
    def get_selection(self) -> tuple[str, str]:
        """Get current projection type and axis selection.
        
        Returns
        -------
        tuple[str, str]
            (projection_type, projection_axis) e.g., ("mean", "t")
        """
        projection_map = {
            "Raw": "raw",
            "Mean": "mean",
            "Std Dev": "std",
            "Min": "min",
            "Max": "max",
        }
        projection_type = projection_map.get(self.projection_combo.currentText(), "raw")
        axis_text = self.axis_combo.currentText()
        projection_axis = "t" if "Time" in axis_text else "z"
        return (projection_type, projection_axis)
