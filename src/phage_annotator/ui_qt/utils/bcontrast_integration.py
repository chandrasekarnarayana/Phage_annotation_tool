"""Integration module for keyboard shortcuts and visual indicators into the main window.

This module handles wiring of the keyboard shortcut system and visual indicator
widgets into the KeypointAnnotator main window, providing seamless integration
with existing UI and display control systems.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Optional
from matplotlib.backends.qt_compat import QtWidgets, QtCore

if TYPE_CHECKING:
    # Avoid circular imports by using TYPE_CHECKING
    from phage_annotator.ui_qt.main_window import KeypointAnnotator

from phage_annotator.ui_qt.utils.keyboard_shortcuts import KeyboardShortcutManager
from phage_annotator.ui_qt.utils.visual_indicators import StatusIndicatorBar


class KeyboardShortcutIntegration:
    """Integration handler for keyboard shortcuts in the main window."""
    
    @staticmethod
    def install_shortcuts(main_window: KeypointAnnotator) -> KeyboardShortcutManager:
        """Install keyboard shortcuts into the main window.
        
        Args:
            main_window: The KeypointAnnotator window instance
            
        Returns:
            The initialized KeyboardShortcutManager instance
        """
        # KeyboardShortcutManager already registers the default action set.
        manager = KeyboardShortcutManager(main_window)

        # Store reference for later access
        main_window._keyboard_shortcut_manager = manager
        
        return manager


class VisualIndicatorIntegration:
    """Integration handler for visual indicators in the main window status bar."""
    
    @staticmethod
    def install_status_indicators(main_window: KeypointAnnotator) -> StatusIndicatorBar:
        """Install visual indicator bar to the status bar.
        
        Args:
            main_window: The KeypointAnnotator window instance
            
        Returns:
            The initialized StatusIndicatorBar instance
        """
        status_bar = main_window.statusBar()
        if status_bar is None:
            raise RuntimeError("Status bar not initialized. Call this after UI setup.")
        
        # Create the indicator bar
        indicator_bar = StatusIndicatorBar()
        
        # Add to permanent widgets (right side of status bar)
        status_bar.addPermanentWidget(indicator_bar)
        
        # Connect display controller signals to update indicators
        # This requires the display controller to be available
        if hasattr(main_window, "display_controller"):
            controller = main_window.display_controller
            
            # Connect modality change signal
            if hasattr(controller, "modality_changed"):
                controller.modality_changed.connect(
                    lambda modality: indicator_bar.update_modality(modality)
                )
            
            # Connect sync state changes
            if hasattr(controller, "sync_state_changed"):
                controller.sync_state_changed.connect(
                    lambda state: indicator_bar.update_sync_state(state)
                )
            
            # Connect display mode changes
            if hasattr(controller, "display_mode_changed"):
                controller.display_mode_changed.connect(
                    lambda mode: indicator_bar.update_display_mode(mode)
                )
        
        # Store reference for later access
        main_window._status_indicator_bar = indicator_bar
        
        return indicator_bar
    
    @staticmethod
    def add_help_menu_item(main_window: KeypointAnnotator) -> None:
        """Add a Help menu item to show keyboard shortcuts.
        
        Args:
            main_window: The KeypointAnnotator window instance
        """
        # Find Menu Bar
        menu_bar = main_window.menuBar()
        if menu_bar is None:
            return
        
        # Find or create Help menu
        help_menu = None
        for action in menu_bar.actions():
            text = action.text().replace("&", "").strip().lower()
            if action.menu() is not None and text == "help":
                help_menu = action.menu()
                break
        
        if help_menu is None:
            help_menu = menu_bar.addMenu("Help")
        
        # Add Keyboard Shortcuts item
        if hasattr(main_window, "_keyboard_shortcut_manager"):
            manager = main_window._keyboard_shortcut_manager
            shortcuts_action = help_menu.addAction("Keyboard Shortcuts")
            shortcuts_action.triggered.connect(
                lambda: manager.show_shortcuts_help()
            )
        
        # Add separator if not the first menu item
        if help_menu.actions():
            help_menu.addSeparator()


def integrate_b_contrast_features(main_window: KeypointAnnotator) -> None:
    """Main integration point for all B&C features into the main window.
    
    This function should be called after UI setup (_setup_ui) is complete
    but before the window is shown.
    
    Args:
        main_window: The KeypointAnnotator window instance
    """
    # Install keyboard shortcuts system
    try:
        shortcut_manager = KeyboardShortcutIntegration.install_shortcuts(main_window)
        print("[B&C Integration] Keyboard shortcuts installed successfully")
    except Exception as e:
        print(f"[B&C Integration] Warning: Failed to install keyboard shortcuts: {e}")
        shortcut_manager = None
    
    # Install visual indicators in status bar only when explicitly enabled.
    # Default behavior keeps status bar transient/minimal to avoid crowding.
    try:
        settings = getattr(main_window, "_settings", None)
        status_minimal_mode = bool(
            settings.value("statusBarMinimalMode", True, type=bool)
            if settings is not None
            else True
        )
        indicators_enabled = bool(
            settings.value("statusIndicatorBarEnabled", False, type=bool)
            if settings is not None
            else False
        )
        # Keep the main status bar uncluttered by default.
        # Require an explicit second opt-in for embedding visual chips there.
        embed_in_status = bool(
            settings.value("statusIndicatorBarInStatusBar", False, type=bool)
            if settings is not None
            else False
        )
        if (not status_minimal_mode) and indicators_enabled and embed_in_status:
            if main_window.statusBar() is not None:
                VisualIndicatorIntegration.install_status_indicators(main_window)
                print("[B&C Integration] Visual indicators installed successfully")
            else:
                print("[B&C Integration] Warning: Status bar not available for indicators")
    except Exception as e:
        print(f"[B&C Integration] Warning: Failed to install visual indicators: {e}")
    
    # Add help menu item for keyboard shortcuts
    try:
        if shortcut_manager:
            VisualIndicatorIntegration.add_help_menu_item(main_window)
            print("[B&C Integration] Help menu item added successfully")
    except Exception as e:
        print(f"[B&C Integration] Warning: Failed to add help menu item: {e}")
    
    print("[B&C Integration] B&C feature integration complete")


# Placeholder methods for main window integration tests
# These should be replaced with actual implementations in the main window

def _placeholder_switch_modality(main_window: KeypointAnnotator, modality_index: int) -> None:
    """Placeholder for modality switching. Replace with actual implementation."""
    print(f"[Placeholder] Switch to modality {modality_index + 1}")


def _placeholder_open_contrast_dialog(main_window: KeypointAnnotator) -> None:
    """Placeholder for opening contrast dialog. Replace with actual implementation."""
    print("[Placeholder] Open contrast dialog")


def _placeholder_reset_contrast(main_window: KeypointAnnotator) -> None:
    """Placeholder for resetting contrast. Replace with actual implementation."""
    print("[Placeholder] Reset contrast")


def _placeholder_auto_contrast(main_window: KeypointAnnotator) -> None:
    """Placeholder for auto-adjusting contrast. Replace with actual implementation."""
    print("[Placeholder] Auto-adjust contrast")


def _placeholder_toggle_playback(main_window: KeypointAnnotator) -> None:
    """Placeholder for playback toggle. Replace with actual implementation."""
    print("[Placeholder] Toggle playback")


def _placeholder_step_frame(main_window: KeypointAnnotator, direction: int) -> None:
    """Placeholder for frame stepping. Replace with actual implementation."""
    direction_str = "next" if direction > 0 else "previous"
    print(f"[Placeholder] Go to {direction_str} frame")
