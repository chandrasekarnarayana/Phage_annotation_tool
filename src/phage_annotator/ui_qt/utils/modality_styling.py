"""Visual styling system for active/inactive modality indicators.

Provides color schemes and styling for:
- Active modality highlighting
- Inactive modality muting
- Visual state indicators (sync, locked, etc.)
"""

from __future__ import annotations

from matplotlib.backends.qt_compat import QtGui


class ModalityStyleScheme:
    """Color scheme and styling constants for modality UI elements."""

    # Active modality colors
    ACTIVE_NAME_COLOR = QtGui.QColor("#000000")
    ACTIVE_BG_COLOR = QtGui.QColor("#e8f4f8")
    ACTIVE_BORDER_COLOR = QtGui.QColor("#2c95a8")
    ACTIVE_BORDER_WIDTH = 2

    # Inactive modality colors
    INACTIVE_NAME_COLOR = QtGui.QColor("#666666")
    INACTIVE_BG_COLOR = QtGui.QColor("#f5f5f5")
    INACTIVE_BORDER_COLOR = QtGui.QColor("#cccccc")
    INACTIVE_BORDER_WIDTH = 1

    # Sync state colors
    SYNC_NONE_COLOR = QtGui.QColor("#cccccc")      # Gray - no sync
    SYNC_VMIN_COLOR = QtGui.QColor("#ff9800")      # Orange - partial
    SYNC_VMAX_COLOR = QtGui.QColor("#ff9800")      # Orange - partial
    SYNC_BOTH_COLOR = QtGui.QColor("#4caf50")      # Green - full sync
    SYNC_CONTRAST_COLOR = QtGui.QColor("#2196f3")  # Blue - all contrast

    # Lock/enable state colors
    LOCKED_COLOR = QtGui.QColor("#f44336")         # Red - locked
    ENABLED_COLOR = QtGui.QColor("#4caf50")        # Green - enabled

    @classmethod
    def get_active_stylesheet(cls, bg_color: bool = True) -> str:
        """Get stylesheet for active modality.
        
        Returns
        -------
        str
            Qt stylesheet for active state
        """
        if bg_color:
            return f"""
                QWidget {{
                    background-color: {cls.ACTIVE_BG_COLOR.name()};
                    border: {cls.ACTIVE_BORDER_WIDTH}px solid {cls.ACTIVE_BORDER_COLOR.name()};
                    border-radius: 4px;
                    padding: 4px;
                }}
                QLabel {{
                    color: {cls.ACTIVE_NAME_COLOR.name()};
                    font-weight: bold;
                }}
            """
        return f"""
            QLabel {{
                color: {cls.ACTIVE_NAME_COLOR.name()};
                font-weight: bold;
            }}
        """

    @classmethod
    def get_inactive_stylesheet(cls, bg_color: bool = True) -> str:
        """Get stylesheet for inactive modality.
        
        Returns
        -------
        str
            Qt stylesheet for inactive state
        """
        if bg_color:
            return f"""
                QWidget {{
                    background-color: {cls.INACTIVE_BG_COLOR.name()};
                    border: {cls.INACTIVE_BORDER_WIDTH}px solid {cls.INACTIVE_BORDER_COLOR.name()};
                    border-radius: 4px;
                    padding: 4px;
                }}
                QLabel {{
                    color: {cls.INACTIVE_NAME_COLOR.name()};
                }}
            """
        return f"""
            QLabel {{
                color: {cls.INACTIVE_NAME_COLOR.name()};
            }}
        """

    @classmethod
    def get_sync_state_color(cls, sync_state: str) -> QtGui.QColor:
        """Get color for a sync state.
        
        Parameters
        ----------
        sync_state : str
            Sync state code (NONE, VMIN, VMAX, VMIN+VMAX, CONTRAST)
        
        Returns
        -------
        QColor
            Color for the sync state
        """
        if sync_state == "NONE":
            return cls.SYNC_NONE_COLOR
        elif sync_state in ["VMIN", "VMAX"]:
            return cls.SYNC_VMIN_COLOR
        elif sync_state == "VMIN+VMAX":
            return cls.SYNC_BOTH_COLOR
        elif sync_state == "CONTRAST":
            return cls.SYNC_CONTRAST_COLOR
        return cls.SYNC_NONE_COLOR


class ModalityVisualState:
    """Helper class for managing visual state of a modality indicator widget."""

    def __init__(self, widget=None, is_active: bool = False):
        """Initialize visual state manager.
        
        Parameters
        ----------
        widget : QWidget, optional
            Widget to apply styling to
        is_active : bool
            Whether the modality is active
        """
        self.widget = widget
        self.is_active = is_active

    def set_active(self) -> None:
        """Mark modality as active and apply styling."""
        self.is_active = True
        if self.widget:
            self.widget.setStyleSheet(ModalityStyleScheme.get_active_stylesheet())

    def set_inactive(self) -> None:
        """Mark modality as inactive and apply styling."""
        self.is_active = False
        if self.widget:
            self.widget.setStyleSheet(ModalityStyleScheme.get_inactive_stylesheet())

    def toggle_active(self) -> None:
        """Toggle active state and update styling."""
        if self.is_active:
            self.set_inactive()
        else:
            self.set_active()
