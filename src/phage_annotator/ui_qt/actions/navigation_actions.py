"""Navigation-related actions."""

from __future__ import annotations

from matplotlib.backends.qt_compat import QtWidgets


class NavigationActionsMixin:
    """Frame/Z navigation dialogs and command execution."""

    def _execute_navigation_command(self, command) -> None:
        """Execute a navigation command and refresh undo/redo state."""
        if not self.controller.execute_view_command(command):
            self._status_warning("Navigation target is out of range.", source="navigation")
            return
        if hasattr(self, "t_slider"):
            target_t = int(getattr(self.controller.view_state, "t", self.t_slider.value()))
            if self.t_slider.value() != target_t:
                self.t_slider.setValue(target_t)
        if hasattr(self, "z_slider"):
            target_z = int(getattr(self.controller.view_state, "z", self.z_slider.value()))
            if self.z_slider.value() != target_z:
                self.z_slider.setValue(target_z)
        self.undo_act.setEnabled(self.controller.can_undo())
        self.redo_act.setEnabled(self.controller.can_redo())
        if hasattr(self, "_update_status"):
            self._update_status()
        else:
            self._request_ui_refresh("navigation-actions")

    def _jump_to_frame_dialog(self) -> None:
        """Prompt for a frame index and navigate via command stack."""
        max_frame = int(max(1, self.primary_image.array.shape[0]))
        current_frame = int(self.t_slider.value()) + 1
        target_frame, ok = QtWidgets.QInputDialog.getInt(
            self,
            "Jump to Frame",
            f"Frame (1-{max_frame}):",
            current_frame,
            1,
            max_frame,
            1,
        )
        if not ok:
            return
        target_t = int(target_frame) - 1
        if target_t == int(self.t_slider.value()):
            return
        from phage_annotator.session.navigation_commands import JumpToFrameCommand

        self._execute_navigation_command(
            JumpToFrameCommand(self.controller, self.primary_image.id, target_t=target_t)
        )

    def _jump_to_z_dialog(self) -> None:
        """Prompt for a Z slice index and navigate via command stack."""
        max_z = int(max(1, self.primary_image.array.shape[1]))
        current_z = int(self.z_slider.value()) + 1
        target_slice, ok = QtWidgets.QInputDialog.getInt(
            self,
            "Jump to Z Slice",
            f"Z slice (1-{max_z}):",
            current_z,
            1,
            max_z,
            1,
        )
        if not ok:
            return
        target_z = int(target_slice) - 1
        if target_z == int(self.z_slider.value()):
            return
        from phage_annotator.session.navigation_commands import JumpToZCommand

        self._execute_navigation_command(
            JumpToZCommand(self.controller, self.primary_image.id, target_z=target_z)
        )
