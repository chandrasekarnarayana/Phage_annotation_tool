"""Project save/load persistence helpers."""

from __future__ import annotations

import pathlib
from typing import Dict, List, Optional

from matplotlib.backends.qt_compat import QtWidgets

from phage_annotator.io.projects import load_project, save_project
from phage_annotator.roi.manager import Roi


class SessionProjectPersistenceMixin:
    """Mixin for project save and load payload persistence."""

    def set_dirty(self, dirty: bool = True) -> None:
        """Mark the session as dirty or clean."""
        from phage_annotator.session.signal_hub import emit_state_changed

        if self.session_state.dirty == dirty:
            return
        self.session_state.dirty = dirty
        emit_state_changed(self)

    def set_project_path(self, path: Optional[pathlib.Path]) -> None:
        """Set the current project path."""
        from phage_annotator.session.signal_hub import emit_state_changed

        if self.session_state.project_path == path:
            return
        self.session_state.project_path = path
        emit_state_changed(self)

    def set_project_save_time(self, ts: Optional[float]) -> None:
        """Set the project save timestamp."""
        from phage_annotator.session.signal_hub import emit_state_changed

        if self.session_state.project_save_time == ts:
            return
        self.session_state.project_save_time = ts
        emit_state_changed(self)

    def set_last_folder(self, folder: Optional[pathlib.Path]) -> None:
        """Update the last-used folder."""
        from phage_annotator.session.signal_hub import emit_state_changed

        if self.session_state.last_folder == folder:
            return
        self.session_state.last_folder = folder
        emit_state_changed(self)

    def set_recent_images(self, recent: List[str]) -> None:
        """Update the recent images list."""
        from phage_annotator.session.signal_hub import emit_state_changed

        self.session_state.recent_images = list(recent)
        emit_state_changed(self)

    def save_project(
        self,
        parent: QtWidgets.QWidget,
        path: pathlib.Path,
        settings: dict,
        rois_by_image: Optional[Dict[int, List[Roi]]] = None,
    ) -> None:
        """Persist the current project payload to disk."""
        from phage_annotator.data.display_mapping import mapping_to_dict

        display_mappings: Dict[int, Dict[str, dict]] = {}
        for image_id, panels in self.display_mapping.per_image.items():
            display_mappings[image_id] = {panel: mapping_to_dict(mapping) for panel, mapping in panels.items()}
        save_project(
            path,
            self.session_state.images,
            self.session_state.annotations,
            settings,
            display_mappings,
            rois_by_image,
            self.session_state.threshold_configs_by_image,
            self.session_state.particles_configs_by_image,
            self.session_state.annotation_imports,
            modality_manager=getattr(self.session_state, "modality_manager", None),
            channel_display_settings=getattr(self.session_state, "channel_display_settings", None),
        )
        self.session_state.project_path = path
        self.session_state.project_save_time = path.stat().st_mtime if path.exists() else None
        self.set_dirty(False)

    def _load_project_payload(self, parent: QtWidgets.QWidget, path: pathlib.Path):
        """Load the serialized project payload from disk."""
        try:
            return load_project(path)
        except Exception as exc:
            QtWidgets.QMessageBox.critical(parent, "Load project failed", str(exc))
            return None
