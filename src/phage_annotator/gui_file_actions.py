"""File and folder loading actions (extracted from gui_actions.py).

This mixin handles all file/folder discovery and image loading operations.
It's extracted to reduce the size of gui_actions.py and improve modularity.

Dependencies:
- self.session_controller (SessionController instance)
- self.job_manager (JobManager instance)
- self._set_status (method to set status bar)
"""

from __future__ import annotations

import pathlib
from typing import List

from matplotlib.backends.qt_compat import QtWidgets

from phage_annotator.logger import get_logger

LOGGER = get_logger(__name__)


class FileActionsMixin:
    """Mixin for file and folder loading operations."""

    def _open_files(self) -> None:
        """Open a file dialog to load individual TIFF images."""
        file_dialog = QtWidgets.QFileDialog(self)
        file_dialog.setFileMode(QtWidgets.QFileDialog.FileMode.ExistingFiles)
        file_dialog.setNameFilters(["TIFF Images (*.tif *.tiff *.ome.tiff)"])

        if not file_dialog.exec():
            return

        paths = [pathlib.Path(p) for p in file_dialog.selectedFiles()]
        if not paths:
            return

        self.session_controller.load_images(paths)
        self._set_status(f"Loaded {len(paths)} image(s)")

    def _open_folder(self) -> None:
        """Open a folder dialog to discover and load all TIFF images in a folder."""
        folder = QtWidgets.QFileDialog.getExistingDirectory(
            self, "Open Folder with TIFF Images", str(pathlib.Path.home())
        )
        if not folder:
            return

        folder_path = pathlib.Path(folder)
        tiff_paths = list(folder_path.glob("**/*.tif*"))

        if not tiff_paths:
            self._set_status("No TIFF images found in folder")
            return

        tiff_paths.sort()
        self.session_controller.load_images(tiff_paths)
        self._set_status(f"Loaded {len(tiff_paths)} image(s) from folder")

    def _recent_limit(self) -> int:
        """Maximum number of recent images to track."""
        return 10

    def _load_recent_images(self) -> List[str]:
        """Load list of recent image paths from session state.

        Returns
        -------
        list[str]
            List of recent file paths.
        """
        return self.session_controller.state.recent_images

    def _add_recent_image(self, path: str) -> None:
        """Add an image path to the recent images list.

        Parameters
        ----------
        path : str
            Path to add.
        """
        recent = self._load_recent_images()
        if path in recent:
            recent.remove(path)
        recent.insert(0, path)
        # Trim to limit
        recent[:] = recent[: self._recent_limit()]
        self.session_controller.state.recent_images = recent
        self._update_recent_menu()

    def _update_recent_menu(self) -> None:
        """Rebuild the 'Recent Images' menu from session state.

        This is called after loading images or updating the recent list.
        The actual menu wiring is in gui_ui_setup.py.
        """
        recent = self._load_recent_images()
        # Menu updates are handled by the UI setup; this ensures consistency
        LOGGER.debug(f"Recent images menu updated: {len(recent)} items")

    def _clear_cache(self) -> None:
        """Clear all cached projections and pyramids from memory."""
        self.session_controller.clear_caches()
        self._set_status("Cache cleared")
