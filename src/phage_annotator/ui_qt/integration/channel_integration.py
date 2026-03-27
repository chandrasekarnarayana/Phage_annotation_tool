"""Integration module for wiring channel controls to session state.

This module manages the hookup between ChannelControlPanel signals and updates
to the session's channel display settings and rendering pipeline.
"""

from __future__ import annotations

import logging
from typing import Dict, List, Optional

from matplotlib.backends.qt_compat import QtCore

from phage_annotator.data.channel_display import (
    BlendMode,
    ChannelDisplayState,
    MultiChannelDisplaySettings,
)

logger = logging.getLogger(__name__)


class ChannelPanelIntegration(QtCore.QObject):
    """Integrator for channel panel with session state.
    
    Coordinates:
    - Channel panel signal emissions
    - Session state updates
    - Renderer refresh triggers
    """
    
    # Signals for session observers
    channel_settings_changed = QtCore.pyqtSignal(MultiChannelDisplaySettings)
    
    def __init__(self, controller, refresh_request_callback=None):
        """Initialize channel panel integration.
        
        Parameters
        ----------
        controller : SessionController
            Controller used to persist channel-display state.
        refresh_request_callback : callable, optional
            Optional queued refresh requester. This should schedule a coalesced
            GUI refresh rather than calling renderer refresh directly.
        """
        super().__init__()
        self.controller = controller
        self.refresh_request = refresh_request_callback
        self._channel_settings: Optional[MultiChannelDisplaySettings] = None
    
    def initialize_from_session(self, channel_count: int) -> MultiChannelDisplaySettings:
        """Initialize channel settings from saved session state or defaults.
        
        Parameters
        ----------
        channel_count : int
            Number of channels available.
        
        Returns
        -------
        MultiChannelDisplaySettings
            The initialized settings (also stored internally).
        """
        # Try to restore from session
        if (
            self.controller.session_state.channel_display_settings
            and isinstance(self.controller.session_state.channel_display_settings, dict)
        ):
            try:
                self._channel_settings = MultiChannelDisplaySettings.from_dict(
                    self.controller.session_state.channel_display_settings
                )
                if self._channel_settings.channel_count == channel_count:
                    return self._channel_settings
            except (KeyError, ValueError):
                pass
        
        # Create default settings
        channels = [
            ChannelDisplayState(channel_idx=i)
            for i in range(channel_count)
        ]
        self._channel_settings = MultiChannelDisplaySettings(
            channel_count=channel_count,
            channels=channels,
            blend_mode=BlendMode.NORMAL,
        )
        return self._channel_settings
    
    def on_channel_visibility_changed(self, channel_idx: int, visible: bool) -> None:
        """Handle channel visibility toggled.
        
        Parameters
        ----------
        channel_idx : int
            Index of channel that changed.
        visible : bool
            New visibility state.
        """
        if self._channel_settings is None:
            return
        
        self._channel_settings.set_channel_visible(channel_idx, visible)
        self._save_and_refresh()
    
    def on_channel_opacity_changed(self, channel_idx: int, opacity: float) -> None:
        """Handle channel opacity changed.
        
        Parameters
        ----------
        channel_idx : int
            Index of channel that changed.
        opacity : float
            New opacity value (0-1).
        """
        if self._channel_settings is None:
            return
        
        self._channel_settings.set_channel_opacity(channel_idx, opacity)
        self._save_and_refresh()
    
    def on_channel_lut_changed(self, channel_idx: int, lut_idx: int) -> None:
        """Handle channel LUT changed.
        
        Parameters
        ----------
        channel_idx : int
            Index of channel that changed.
        lut_idx : int
            New LUT index.
        """
        if self._channel_settings is None:
            return
        
        self._channel_settings.set_channel_lut(channel_idx, lut_idx)
        self._save_and_refresh()
    
    def on_blend_mode_changed(self, blend_mode: str) -> None:
        """Handle blend mode changed.
        
        Parameters
        ----------
        blend_mode : str
            New blend mode value (e.g., "normal", "screen", "add").
        """
        if self._channel_settings is None:
            return
        
        try:
            self._channel_settings.blend_mode = BlendMode(blend_mode)
        except ValueError:
            self._channel_settings.blend_mode = BlendMode.NORMAL
        
        self._save_and_refresh()
    
    def _save_and_refresh(self) -> None:
        """Save settings to session and trigger refresh."""
        if self._channel_settings is None:
            return
        
        # Save to session state
        self.controller.set_channel_display_settings_value(
            self._channel_settings.to_dict()
        )
        
        # Emit signal for observers
        self.channel_settings_changed.emit(self._channel_settings)
        
        # Display changes should normally flow through controller.display_changed.
        # If a caller provides an explicit refresh requester, require it to be
        # a queued refresh path rather than a direct canvas redraw.
        if self.refresh_request is not None:
            try:
                self.refresh_request()
            except Exception:
                logger.warning("Failed to request queued refresh after channel settings update", exc_info=True)
    
    def get_channel_settings(self) -> Optional[MultiChannelDisplaySettings]:
        """Get current channel display settings.
        
        Returns
        -------
        MultiChannelDisplaySettings or None
            Current settings, or None if not initialized.
        """
        return self._channel_settings
    
    def reset_to_defaults(self, channel_count: int) -> None:
        """Reset all channels to default state.
        
        Parameters
        ----------
        channel_count : int
            Number of channels to initialize with.
        """
        channels = [
            ChannelDisplayState(channel_idx=i)
            for i in range(channel_count)
        ]
        self._channel_settings = MultiChannelDisplaySettings(
            channel_count=channel_count,
            channels=channels,
            blend_mode=BlendMode.NORMAL,
        )
        self._save_and_refresh()
