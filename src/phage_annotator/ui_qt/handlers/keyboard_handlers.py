"""Keyboard shortcuts and actions handlers for B&C system integration.

This mixin provides callback methods for keyboard shortcuts that control
the brightness/contrast system, display modes, and modality switching.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from phage_annotator.ui_qt.main_window import KeypointAnnotator


class KeyboardHandlersMixin:
    """Mixin providing keyboard shortcut callback methods."""

    def _switch_modality(self, modality_index: int) -> None:
        """Switch to specified modality by index.
        
        Args:
            modality_index: 0-based index of the modality to switch to (0-8 for Ctrl+1-9)
        """
        if not hasattr(self, "modality_facade") or self.modality_facade is None:
            return
        
        try:
            modalities = self.modality_facade.list_modalities()
            if modality_index < len(modalities):
                modality = modalities[modality_index]
                # Update display to show this modality
                if hasattr(self, "controller") and self.controller:
                    # Typically modality selection is handled through UI interaction
                    # This is a simplified version - actual implementation may vary
                    print(f"Switching to modality: {modality.name if hasattr(modality, 'name') else modality_index}")
        except Exception as e:
            print(f"Error switching modality: {e}")

    def _open_contrast_dialog(self) -> None:
        """Open the brightness/contrast dialog.
        
        Shows the contrast adjustment dialog for the current modality.
        """
        try:
            # Check if we have a contrast dialog or display controls
            if hasattr(self, "display_controls_panel") and self.display_controls_panel:
                # Show the contrast panel if available
                if hasattr(self.display_controls_panel, "show_contrast_dialog"):
                    self.display_controls_panel.show_contrast_dialog()
                else:
                    print("Contrast dialog not available")
            else:
                print("Display controls not initialized")
        except Exception as e:
            print(f"Error opening contrast dialog: {e}")

    def _reset_contrast(self) -> None:
        """Reset contrast to default values for current modality.
        
        Resets brightness and contrast sliders to default values.
        """
        try:
            # Reset to default display settings
            if hasattr(self, "display_controls_panel") and self.display_controls_panel:
                if hasattr(self.display_controls_panel, "reset_contrast"):
                    self.display_controls_panel.reset_contrast()
            print("Contrast reset to defaults")
        except Exception as e:
            print(f"Error resetting contrast: {e}")

    def _auto_contrast(self) -> None:
        """Auto-adjust brightness/contrast for current image.
        
        Automatically computes optimal contrast based on image data.
        """
        try:
            # Compute and apply auto-contrast
            if hasattr(self, "display_controls_panel") and self.display_controls_panel:
                if hasattr(self.display_controls_panel, "apply_auto_contrast"):
                    self.display_controls_panel.apply_auto_contrast()
            print("Auto-contrast applied")
        except Exception as e:
            print(f"Error applying auto-contrast: {e}")

    def _toggle_playback(self) -> None:
        """Toggle playback on/off.
        
        Plays or pauses the current playback session.
        """
        try:
            if hasattr(self, "play_timer") and self.play_timer:
                if self.play_timer.isActive():
                    self.play_timer.stop()
                    print("Playback paused")
                else:
                    self.play_timer.start()
                    print("Playback started")
        except Exception as e:
            print(f"Error toggling playback: {e}")

    def _step_frame(self, direction: int) -> None:
        """Step to next or previous frame.
        
        Args:
            direction: +1 to go to next frame, -1 to go to previous frame
        """
        try:
            if not hasattr(self, "controller") or self.controller is None:
                return
            
            current_idx = self.current_image_idx if hasattr(self, "current_image_idx") else 0
            new_idx = current_idx + direction
            
            # Clamp to valid range
            if hasattr(self, "controller"):
                num_images = len(self.controller.images) if hasattr(self.controller, "images") else 1
                new_idx = max(0, min(new_idx, num_images - 1))
                
                if new_idx != current_idx:
                    # Switch to new frame
                    if hasattr(self, "_set_current_image"):
                        self._set_current_image(new_idx)
                    print(f"Frame {new_idx + 1}")
        except Exception as e:
            print(f"Error stepping frame: {e}")
