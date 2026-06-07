"""Dynamic canvas layout manager for multi-modality views.

This module provides a flexible canvas management system that dynamically
arranges multiple modality views in aesthetic layouts. It supports:
- Grid layout (2×2, 3×3, etc.)
- Horizontal/vertical split layouts
- Single modality focus mode
- Dynamic resize and reflow

Phase δ: VSCode-style dynamic canvas management.
"""

from __future__ import annotations

from PyQt5 import QtWidgets, QtCore
from enum import Enum
from matplotlib.backends.backend_qt5agg import FigureCanvasQTAgg
from matplotlib.figure import Figure
from typing import Dict, List, Optional, Tuple
import matplotlib.pyplot as plt


class LayoutMode(Enum):
    """Canvas layout strategies for multiple modalities."""
    
    SINGLE = "single"  # Single large view (focus mode)
    HORIZONTAL = "horizontal"  # Side-by-side horizontal split
    VERTICAL = "vertical"  # Top-bottom vertical split
    GRID_2X2 = "grid_2x2"  # 2×2 grid (up to 4 modalities)
    GRID_3X2 = "grid_3x2"  # 3×2 grid (up to 6 modalities)
    GRID_3X3 = "grid_3x3"  # 3×3 grid (up to 9 modalities)
    AUTO = "auto"  # Automatically choose best layout based on modality count

class ModalityCanvasView:
    """Single canvas view for one modality with associated matplotlib axes."""
    
    def __init__(
        self,
        modality_idx: int,
        modality_name: str,
        ax: plt.Axes,
        canvas: FigureCanvasQTAgg
    ):
        """Initialize a canvas view for a single modality.
        
        Parameters
        ----------
        modality_idx : int
            Index of the modality in the ModalityManager.
        modality_name : str
            Display name of the modality.
        ax : plt.Axes
            Matplotlib axes for rendering this modality.
        canvas : FigureCanvasQTAgg
            Shared canvas containing this axes.
        """
        self.modality_idx = modality_idx
        self.modality_name = modality_name
        self.ax = ax
        self.canvas = canvas
        self._is_active = False
        self._setup_axes()
    
    def _setup_axes(self) -> None:
        """Configure axes appearance with visible coordinate ticks."""
        self.ax.set_aspect('equal')
        self.ax.set_title(self.modality_name, fontsize=10, pad=5)
        self.ax.tick_params(
            axis='both',
            which='both',
            bottom=True,
            top=False,
            left=True,
            right=False,
            labelbottom=True,
            labelleft=True,
            length=3,
            width=0.8,
            labelsize=8
        )
        # Keep location context visible for annotation/navigation.
        self.ax.set_xlabel("X", fontsize=8, labelpad=2)
        self.ax.set_ylabel("Y", fontsize=8, labelpad=2)
    
    def set_active(self, active: bool) -> None:
        """Highlight this view as the active modality.
        
        Parameters
        ----------
        active : bool
            Whether this modality is currently active.
        """
        self._is_active = active
        # Visual feedback: thicker border for active view
        if active:
            for spine in self.ax.spines.values():
                spine.set_edgecolor('#0078D4')  # Blue highlight
                spine.set_linewidth(2.5)
        else:
            for spine in self.ax.spines.values():
                spine.set_edgecolor('#CCCCCC')  # Gray border
                spine.set_linewidth(1.0)
    
    def update_title(self, title: str) -> None:
        """Update the modality title display.
        
        Parameters
        ----------
        title : str
            New title to display.
        """
        self.modality_name = title
        self.ax.set_title(title, fontsize=10, pad=5)
    
    def clear(self) -> None:
        """Clear all content from this view."""
        self.ax.clear()
        self._setup_axes()

import phage_annotator.ui_qt.widgets.canvas_manager_core as _canvas_core
import phage_annotator.ui_qt.widgets.canvas_manager_layout as _canvas_layout
from phage_annotator.ui_qt.widgets.canvas_manager_core import CanvasManagerCoreMixin
from phage_annotator.ui_qt.widgets.canvas_manager_layout import CanvasManagerLayoutMixin

_canvas_core.LayoutMode = LayoutMode
_canvas_core.ModalityCanvasView = ModalityCanvasView
_canvas_layout.LayoutMode = LayoutMode
_canvas_layout.ModalityCanvasView = ModalityCanvasView


class ModalityCanvasManager(CanvasManagerCoreMixin, CanvasManagerLayoutMixin, QtWidgets.QWidget):
    """Dynamic canvas layout manager for multiple modality views.

Automatically arranges modalities in aesthetic layouts and handles
dynamic resize, focus mode, and modality switching.

Signals
-------
modality_clicked : pyqtSignal(int)
    Emitted when a modality canvas is clicked (carries modality index).
layout_changed : pyqtSignal(str)
    Emitted when the layout mode changes (carries layout mode string).

Example
-------
>>> manager = ModalityCanvasManager()
>>> manager.set_modalities(["TIRF", "Confocal", "Brightfield"])
>>> manager.set_layout_mode(LayoutMode.GRID_2X2)
>>> manager.set_active_modality(0)"""

    modality_clicked = QtCore.pyqtSignal(int)
    layout_changed = QtCore.pyqtSignal(str)
