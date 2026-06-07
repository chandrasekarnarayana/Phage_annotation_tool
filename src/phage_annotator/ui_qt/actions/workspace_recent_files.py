"""Workspace, recent-file, and annotation-load actions."""

from __future__ import annotations

import pathlib
from typing import List, Optional

import numpy as np
from matplotlib.backends.qt_compat import QtCore, QtGui, QtWidgets

from phage_annotator.io.metadata.reader import MetadataBundle
from phage_annotator.session.signal_hub import emit_annotations_changed
from phage_annotator.ui_qt.rendering.lut_manager import lut_names
from phage_annotator.ui_qt.utils.image_io import read_metadata

class WorkspaceRecentFilesMixin:
    def _recent_limit(self) -> int:
        """Document the recent_limit flow."""
        return int(self._settings.value("keepRecentImages", 10, type=int))

    def _load_recent_images(self) -> List[str]:
        """Document the load_recent_images flow."""
        recent = self._settings.value("recentImages", [], type=list)
        recent_list = [str(p) for p in recent] if recent else []
        self.controller.set_recent_images(recent_list)
        return recent_list

    def _save_recent_images(self, recent: List[str]) -> None:
        """Document the save_recent_images flow."""
        self._settings.setValue("recentImages", recent)
        self.controller.set_recent_images(recent)

    def _add_recent_images(self, paths: List[pathlib.Path]) -> None:
        """Document the add_recent_images flow."""
        recent = self._load_recent_images()
        for p in paths:
            p_str = str(p)
            if p_str in recent:
                recent.remove(p_str)
            recent.insert(0, p_str)
        limit = self._recent_limit()
        recent = recent[:limit]
        self._save_recent_images(recent)
        self._populate_recent_menu()

    def _populate_recent_menu(self) -> None:
        """Document the populate_recent_menu flow."""
        self.recent_menu.clear()
        recent = self._load_recent_images()
        for path in recent:
            act = self.recent_menu.addAction(path)
            act.triggered.connect(lambda _checked, p=path: self._open_recent_image(p))
        if recent:
            self.recent_menu.addSeparator()
        self.recent_menu.addAction(self.recent_clear_act)

    def _clear_recent_images(self) -> None:
        """Document the clear_recent_images flow."""
        self._save_recent_images([])
        self._populate_recent_menu()

    def _open_recent_image(self, path: str) -> None:
        """Document the open_recent_image flow."""
        p = pathlib.Path(path)
        if not p.exists():
            QtWidgets.QMessageBox.warning(self, "File not found", f"{path} does not exist.")
            self._clear_recent_images()
            return
        self._open_files_from_paths([p])
