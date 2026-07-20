"""Extracted method group 2 for ModalityCanvasManager."""

from __future__ import annotations

from enum import Enum
from typing import Dict, List, Optional, Tuple, TYPE_CHECKING

from matplotlib.backends.backend_qt5agg import FigureCanvasQTAgg
from matplotlib.figure import Figure
from PyQt5 import QtWidgets, QtCore
import matplotlib.pyplot as plt

if TYPE_CHECKING:
    # Runtime bindings for LayoutMode/ModalityCanvasView are injected by
    # phage_annotator.ui_qt.widgets.modality_canvas (which imports this
    # module) to avoid a circular import; this import is for static
    # analysis/type-checking only.
    from phage_annotator.ui_qt.widgets.modality_canvas import (
        LayoutMode,
        ModalityCanvasView,
    )


class CanvasManagerLayoutMixin:
    """Method group 2 extracted from ModalityCanvasManager."""

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
