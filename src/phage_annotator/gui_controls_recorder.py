"""Action recorder handlers."""

from __future__ import annotations

import pathlib

from matplotlib.backends.qt_compat import QtWidgets


class RecorderControlsMixin:
    """Mixin for action recorder handlers."""

    def _toggle_recorder(self, checked: bool) -> None:
        if self.recorder_widget is not None:
            dock = self.panel_docks.get("recorder")
            if dock is not None:
                dock.setVisible(checked)

    def _attach_recorder(self) -> None:
        if self._action_map:
            self.recorder.attach_actions(self._action_map)
        if self.recorder_widget is not None:
            self.recorder_widget.copy_btn.clicked.connect(self.recorder_widget.copy_to_clipboard)
            self.recorder_widget.save_btn.clicked.connect(self._recorder_save)

    def _recorder_save(self) -> None:
        if self._project_path is None:
            QtWidgets.QMessageBox.warning(
                self, "Recorder", "Save the project before saving the recorder log."
            )
            return
        path = self.recorder.save_to_project(self._project_path)
        self._set_status(f"Saved recorder log to {path}")
