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

from enum import Enum
from typing import Dict, List, Optional, Tuple

from matplotlib.backends.backend_qt5agg import FigureCanvasQTAgg
from matplotlib.figure import Figure
from PyQt5 import QtWidgets, QtCore
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


class ModalityCanvasManager(QtWidgets.QWidget):
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
    >>> manager.set_active_modality(0)
    """
    
    modality_clicked = QtCore.pyqtSignal(int)
    layout_changed = QtCore.pyqtSignal(str)
    
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
    
    def set_layout_mode(self, mode: LayoutMode) -> None:
        """Change the canvas layout mode.
        
        Parameters
        ----------
        mode : LayoutMode
            New layout mode.
        """
        if mode == self._layout_mode:
            return
        
        self._layout_mode = mode
        
        # Rebuild with current modalities
        if self._modality_views:
            specs = [
                (view.modality_idx, view.modality_name)
                for view in self._modality_views.values()
            ]
            self.set_modalities(specs)
        
        self.layout_changed.emit(mode.value)
    
    def set_active_modality(self, modality_idx: int) -> None:
        """Set the active modality with visual feedback.
        
        Parameters
        ----------
        modality_idx : int
            Index of the modality to activate.
        """
        if modality_idx == self._active_modality_idx:
            return
        
        self._active_modality_idx = modality_idx
        self._update_active_highlight()
    
    def _update_active_highlight(self) -> None:
        """Update visual highlighting for active modality."""
        for idx, view in self._modality_views.items():
            view.set_active(idx == self._active_modality_idx)
        
        if self._canvas:
            self._canvas.draw_idle()
    
    def get_view(self, modality_idx: int) -> Optional[ModalityCanvasView]:
        """Get the canvas view for a specific modality.
        
        Parameters
        ----------
        modality_idx : int
            Modality index.
        
        Returns
        -------
        ModalityCanvasView or None
            The view if it exists, else None.
        """
        return self._modality_views.get(modality_idx)
    
    def get_all_views(self) -> Dict[int, ModalityCanvasView]:
        """Get all active canvas views.
        
        Returns
        -------
        Dict[int, ModalityCanvasView]
            Dictionary mapping modality index to view.
        """
        return self._modality_views.copy()
    
    def _on_canvas_click(self, event) -> None:
        """Handle click events on the canvas.
        
        Parameters
        ----------
        event : matplotlib.backend_bases.MouseEvent
            Click event.
        """
        if event.inaxes is None:
            return
        
        # Find which modality was clicked
        for idx, view in self._modality_views.items():
            if view.ax == event.inaxes:
                self.modality_clicked.emit(idx)
                self.set_active_modality(idx)
                break
    
    def update_modality_title(self, modality_idx: int, title: str) -> None:
        """Update the title for a specific modality view.
        
        Parameters
        ----------
        modality_idx : int
            Modality index.
        title : str
            New title.
        """
        view = self._modality_views.get(modality_idx)
        if view:
            view.update_title(title)
            if self._canvas:
                self._canvas.draw_idle()
    
    @property
    def canvas(self) -> Optional[FigureCanvasQTAgg]:
        """Get the underlying matplotlib canvas.
        
        Returns
        -------
        FigureCanvasQTAgg or None
            The canvas if created, else None.
        """
        return self._canvas
    
    @property
    def figure(self) -> Optional[Figure]:
        """Get the underlying matplotlib figure.
        
        Returns
        -------
        Figure or None
            The figure if created, else None.
        """
        return self._figure
