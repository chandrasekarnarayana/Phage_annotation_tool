"""Keyboard shortcut management."""

from __future__ import annotations

from typing import Callable, Dict, List, Optional, Tuple

from matplotlib.backends.qt_compat import QtCore, QtGui, QtWidgets

class KeyboardShortcutHandlersMixin:

    def _switch_modality(self, idx: int) -> None:
        """Switch to specified modality."""
        if 0 <= idx < len(getattr(self.main_window, "images", []) or []):
            self.main_window._set_fov(idx)

    def _add_modality(self) -> None:
        """Add new modality (placeholder - requires session integration)."""
        # This will be implemented in main window integration
        pass

    def _remove_modality(self) -> None:
        """Remove current modality (placeholder - requires session integration)."""
        # This will be implemented in main window integration
        pass

    def _rename_modality(self) -> None:
        """Rename current modality (placeholder - requires session integration)."""
        # This will be implemented in main window integration
        pass

    def _open_contrast_dialog(self) -> None:
        """Open contrast adjustment dialog."""
        if hasattr(self.main_window, '_on_contrast_dialog'):
            self.main_window._on_contrast_dialog()

    def _reset_contrast(self) -> None:
        """Reset contrast to default."""
        if hasattr(self.main_window, 'reset_contrast'):
            self.main_window.reset_contrast()

    def _auto_contrast(self) -> None:
        """Apply auto-contrast to current view."""
        if hasattr(self.main_window, '_auto_contrast'):
            self.main_window._auto_contrast()

    def _toggle_playback(self) -> None:
        """Toggle play/pause."""
        if hasattr(self.main_window, 'play_t_btn'):
            self.main_window.play_t_btn.click()

    def _next_frame(self) -> None:
        """Advance to next frame."""
        if hasattr(self.main_window, 't_plus_button'):
            self.main_window.t_plus_button.click()

    def _prev_frame(self) -> None:
        """Go back to previous frame."""
        if hasattr(self.main_window, 't_minus_button'):
            self.main_window.t_minus_button.click()

    def _toggle_zoom_link(self) -> None:
        """Toggle zoom/pan linking between modalities."""
        if hasattr(self.main_window, '_toggle_zoom_link'):
            self.main_window._toggle_zoom_link()

    def _reset_zoom(self) -> None:
        """Reset zoom to fit entire image."""
        if hasattr(self.main_window, '_reset_zoom'):
            self.main_window._reset_zoom()

    def _open_threshold(self) -> None:
        """Open threshold analysis panel."""
        if hasattr(self.main_window, '_open_threshold'):
            self.main_window._open_threshold()

    def _open_particles(self) -> None:
        """Open particle analysis panel."""
        if hasattr(self.main_window, '_open_particles'):
            self.main_window._open_particles()

    def _roi_add(self) -> None:
        """Add ROI from current selection."""
        if hasattr(self.main_window, '_roi_mgr_add'):
            self.main_window._roi_mgr_add()

    def _roi_delete(self) -> None:
        """Delete selected ROI(s)."""
        if hasattr(self.main_window, '_roi_mgr_delete'):
            self.main_window._roi_mgr_delete()

    def _roi_duplicate(self) -> None:
        """Duplicate selected ROI."""
        if hasattr(self.main_window, '_roi_mgr_duplicate'):
            self.main_window._roi_mgr_duplicate()

    def _roi_rename(self) -> None:
        """Rename selected ROI."""
        if hasattr(self.main_window, '_roi_mgr_rename'):
            self.main_window._roi_mgr_rename()

    def _roi_deselect(self) -> None:
        """Deselect ROI without deleting."""
        if hasattr(self.main_window, '_roi_mgr_deselect'):
            self.main_window._roi_mgr_deselect()

    def _roi_update(self) -> None:
        """Update ROI geometry from current selection."""
        if hasattr(self.main_window, '_roi_mgr_update'):
            self.main_window._roi_mgr_update()

    def _roi_bind_to_slice(self) -> None:
        """Bind selected ROI(s) to current slice."""
        if hasattr(self.main_window, '_roi_mgr_batch_bind_to_slice'):
            self.main_window._roi_mgr_batch_bind_to_slice()

    def _roi_undo(self) -> None:
        """Undo last ROI operation."""
        if hasattr(self.main_window, '_roi_mgr_undo'):
            self.main_window._roi_mgr_undo()

    def _roi_redo(self) -> None:
        """Redo last undone ROI operation."""
        if hasattr(self.main_window, '_roi_mgr_redo'):
            self.main_window._roi_mgr_redo()
