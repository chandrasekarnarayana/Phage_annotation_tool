"""Extracted method group 1 for ModalityCanvasManager."""

from __future__ import annotations

from enum import Enum
from typing import Dict, List, Optional, Tuple

from matplotlib.backends.backend_qt5agg import FigureCanvasQTAgg
from matplotlib.figure import Figure
from PyQt5 import QtWidgets, QtCore
import matplotlib.pyplot as plt




class CanvasManagerCoreMixin:
    """Method group 1 extracted from ModalityCanvasManager."""

    def __init__(self, parent: Optional[QtWidgets.QWidget] = None):
        """Initialize the canvas manager.
        
        Parameters
        ----------
        parent : QtWidgets.QWidget, optional
            Parent widget.
        """
        super().__init__(parent)
        self._layout_mode = LayoutMode.AUTO
        self._modality_views: Dict[int, ModalityCanvasView] = {}
        self._active_modality_idx: Optional[int] = None
        self._figure: Optional[Figure] = None
        self._canvas: Optional[FigureCanvasQTAgg] = None
        
        self._init_ui()
    def _init_ui(self) -> None:
        """Initialize the widget UI."""
        layout = QtWidgets.QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)
        
        # Create initial empty canvas
        self._recreate_canvas(1, 1, [])
    def _recreate_canvas(
        self,
        rows: int,
        cols: int,
        modality_specs: List[Tuple[int, str]]
    ) -> None:
        """Recreate the matplotlib figure with new layout.
        
        Parameters
        ----------
        rows : int
            Number of subplot rows.
        cols : int
            Number of subplot columns.
        modality_specs : List[Tuple[int, str]]
            List of (modality_idx, modality_name) tuples.
        """
        # Keep a single figure/canvas instance for the widget lifetime so
        # external renderer, toolbar, and mpl event bindings remain valid.
        if self._figure is None or self._canvas is None:
            self._figure = Figure(figsize=(8, 6), dpi=100)
            self._figure.patch.set_facecolor('#F0F0F0')
            self._canvas = FigureCanvasQTAgg(self._figure)
            self._canvas.mpl_connect('button_press_event', self._on_canvas_click)
            self.layout().addWidget(self._canvas)
        else:
            self._figure.clear()
            self._figure.patch.set_facecolor('#F0F0F0')
        
        # Create subplots and views
        self._modality_views.clear()
        
        if not modality_specs:
            # Empty placeholder
            ax = self._figure.add_subplot(1, 1, 1)
            ax.text(
                0.5, 0.5,
                "No modalities loaded\n\nLoad images to begin",
                ha='center',
                va='center',
                fontsize=14,
                color='#888888'
            )
            ax.set_xlim(0, 1)
            ax.set_ylim(0, 1)
            ax.axis('off')
        else:
            # Create grid of subplots
            for i, (mod_idx, mod_name) in enumerate(modality_specs):
                if i >= rows * cols:
                    break  # Don't exceed grid capacity
                
                ax = self._figure.add_subplot(rows, cols, i + 1)
                view = ModalityCanvasView(mod_idx, mod_name, ax, self._canvas)
                self._modality_views[mod_idx] = view
            
            # Adjust spacing for clean presentation
            self._figure.subplots_adjust(
                left=0.05,
                right=0.95,
                top=0.95,
                bottom=0.05,
                hspace=0.3,
                wspace=0.3
            )
        
        self._canvas.draw()
    def _compute_layout_grid(
        self,
        modality_count: int,
        mode: LayoutMode
    ) -> Tuple[int, int]:
        """Compute optimal grid dimensions for modalities.
        
        Parameters
        ----------
        modality_count : int
            Number of modalities to display.
        mode : LayoutMode
            Layout mode (AUTO will choose based on count).
        
        Returns
        -------
        Tuple[int, int]
            (rows, cols) grid dimensions.
        """
        if mode == LayoutMode.SINGLE:
            return (1, 1)
        elif mode == LayoutMode.HORIZONTAL:
            return (1, min(modality_count, 4))  # Max 4 columns
        elif mode == LayoutMode.VERTICAL:
            return (min(modality_count, 4), 1)  # Max 4 rows
        elif mode == LayoutMode.GRID_2X2:
            return (2, 2)
        elif mode == LayoutMode.GRID_3X2:
            return (2, 3)
        elif mode == LayoutMode.GRID_3X3:
            return (3, 3)
        elif mode == LayoutMode.AUTO:
            # Smart layout selection based on modality count
            if modality_count == 1:
                return (1, 1)
            elif modality_count == 2:
                return (1, 2)
            elif modality_count <= 4:
                return (2, 2)
            elif modality_count <= 6:
                return (2, 3)
            else:
                return (3, 3)
        else:
            return (1, 1)
    def set_modalities(
        self,
        modality_specs: List[Tuple[int, str]],
        grid: Optional[Tuple[int, int]] = None,
    ) -> None:
        """Configure canvas with modalities.
        
        Parameters
        ----------
        modality_specs : List[Tuple[int, str]]
            List of (modality_idx, modality_name) tuples to display.
        """
        if not modality_specs:
            self._recreate_canvas(1, 1, [])
            return
        
        # Compute layout
        if grid is not None:
            rows = max(1, int(grid[0]))
            cols = max(1, int(grid[1]))
        else:
            rows, cols = self._compute_layout_grid(len(modality_specs), self._layout_mode)
        
        # Handle SINGLE mode - only show active or first modality
        if self._layout_mode == LayoutMode.SINGLE:
            if self._active_modality_idx is not None:
                active_spec = [
                    spec for spec in modality_specs
                    if spec[0] == self._active_modality_idx
                ]
                if active_spec:
                    modality_specs = active_spec
                else:
                    modality_specs = [modality_specs[0]]
            else:
                modality_specs = [modality_specs[0]]
        
        # Recreate canvas with new layout
        self._recreate_canvas(rows, cols, modality_specs)
        
        # Restore active state
        if self._active_modality_idx is not None:
            self._update_active_highlight()
