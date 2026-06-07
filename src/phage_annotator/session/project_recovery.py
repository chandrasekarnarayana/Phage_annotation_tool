"""Project relink and recovery helpers."""

from __future__ import annotations

from datetime import datetime
import pathlib
from typing import Dict, Iterable, List, Optional

from matplotlib.backends.qt_compat import QtWidgets

from phage_annotator.annotation.core import Keypoint, keypoints_from_json, save_keypoints_json
from phage_annotator.session.signal_hub import emit_annotations_changed


class SessionProjectRecoveryMixin:
    """Mixin for project relink and recovery workflows."""

    @staticmethod
    def _resolve_project_image_path(entry: Dict[str, object], project_dir: pathlib.Path) -> pathlib.Path:
        """Resolve project image path for the current workflow."""
        raw = pathlib.Path(str(entry.get("path", "")))
        if raw.exists():
            return raw
        rel = entry.get("path_relative")
        if isinstance(rel, str) and rel.strip():
            candidate = (project_dir / rel).resolve()
            if candidate.exists():
                return candidate
        image_name = str(entry.get("image_name", raw.name)).strip()
        if image_name:
            direct = (project_dir / image_name).resolve()
            if direct.exists():
                return direct
            for candidate in project_dir.rglob(image_name):
                if candidate.is_file():
                    return candidate.resolve()
        return raw

    @staticmethod
    def _prompt_relink_missing_images(parent: QtWidgets.QWidget, missing_entries: List[tuple[int, Dict[str, object], pathlib.Path]], *, mode: str = "ask") -> Dict[int, pathlib.Path]:
        """Handle the prompt relink missing images helper flow."""
        if not missing_entries:
            return {}
        relinked: Dict[int, pathlib.Path] = {}
        if mode not in {"ask", "auto", "manual"}:
            mode = "ask"
        resp = QtWidgets.QMessageBox.StandardButton.Yes
        if mode == "ask":
            resp = QtWidgets.QMessageBox.question(
                parent,
                "Missing images",
                f"{len(missing_entries)} project image(s) were not found.\nYes = select one folder for auto-relink\nNo = select each missing file manually",
                QtWidgets.QMessageBox.StandardButton.Yes | QtWidgets.QMessageBox.StandardButton.No | QtWidgets.QMessageBox.StandardButton.Cancel,
                QtWidgets.QMessageBox.StandardButton.Yes,
            )
        elif mode == "manual":
            resp = QtWidgets.QMessageBox.StandardButton.No
        if resp == QtWidgets.QMessageBox.StandardButton.Cancel:
            return relinked
        if resp == QtWidgets.QMessageBox.StandardButton.Yes:
            folder = QtWidgets.QFileDialog.getExistingDirectory(parent, "Select folder containing relocated images", str(pathlib.Path.cwd()))
            if not folder:
                return relinked
            folder_path = pathlib.Path(folder)
            for idx, entry, fallback in missing_entries:
                image_name = str(entry.get("image_name", fallback.name)).strip()
                if not image_name:
                    continue
                direct = (folder_path / image_name).resolve()
                if direct.exists() and direct.is_file():
                    relinked[idx] = direct
                    continue
                matches = [p for p in folder_path.rglob(image_name) if p.is_file()]
                if matches:
                    relinked[idx] = matches[0].resolve()
            return relinked
        for idx, entry, fallback in missing_entries:
            image_name = str(entry.get("image_name", fallback.name)).strip()
            start_dir = str(pathlib.Path.cwd() / image_name) if image_name else str(pathlib.Path.cwd())
            selected, _ = QtWidgets.QFileDialog.getOpenFileName(
                parent,
                f"Locate image: {image_name or fallback.name}",
                start_dir,
                "Image files (*.tif *.tiff *.ome.tif *.ome.tiff);;All files (*)",
            )
            if selected:
                selected_path = pathlib.Path(selected).resolve()
                if selected_path.exists() and selected_path.is_file():
                    relinked[idx] = selected_path
        return relinked

    def autosave_if_needed(self, parent: QtWidgets.QWidget, current_keypoints) -> Optional[pathlib.Path]:
        """Run the autosave if needed workflow."""
        if not self._settings.value("autosaveRecoveryEnabled", True, type=bool):
            return None
        if not self.session_state.dirty or self.session_state.project_path is None:
            return None
        recovery_dir = self.session_state.project_path.parent / ".recovery"
        recovery_dir.mkdir(parents=True, exist_ok=True)
        ts = datetime.now().strftime("%Y%m%d_%H%M%S")
        primary_name = pathlib.Path(self.session_state.images[self.session_state.active_primary_id].name).stem
        recovery_path = recovery_dir / f"{ts}_{primary_name}.annotations.json"
        save_keypoints_json(current_keypoints(), recovery_path)
        return recovery_path

    def check_recovery(self, parent: QtWidgets.QWidget) -> None:
        """Check recovery for the current workflow."""
        latest = self.find_recovery_file(None)
        if latest is None:
            return
        resp = QtWidgets.QMessageBox.question(parent, "Recovery available", f"A recovery file newer than the project was found:\n{latest.name}\nRestore it?")
        if resp != QtWidgets.QMessageBox.StandardButton.Yes:
            return
        try:
            self.apply_recovery_points(keypoints_from_json(latest))
            self.set_dirty(True)
        except Exception as exc:
            QtWidgets.QMessageBox.critical(parent, "Recovery failed", str(exc))

    def find_recovery_file(self, current_keypoints) -> Optional[pathlib.Path]:
        """Find recovery file for the current workflow."""
        if not self._settings.value("autosaveRecoveryEnabled", True, type=bool):
            return None
        if self.session_state.project_path is None or self.session_state.project_save_time is None:
            return None
        recovery_dir = self.session_state.project_path.parent / ".recovery"
        if not recovery_dir.exists():
            return None
        candidates = sorted(recovery_dir.glob("*.annotations.json"), key=lambda p: p.stat().st_mtime, reverse=True)
        if not candidates:
            return None
        latest = candidates[0]
        return latest if latest.stat().st_mtime > self.session_state.project_save_time else None

    def restore_recovery(self, path: pathlib.Path) -> None:
        """Restore recovery for the current workflow."""
        self.apply_recovery_points(keypoints_from_json(path))
        self.set_dirty(True)

    def apply_recovery_points(self, kps: Iterable[Keypoint]) -> None:
        """Apply recovery points for the current workflow."""
        by_name: Dict[str, List[Keypoint]] = {}
        for kp in kps:
            by_name.setdefault(kp.image_name, []).append(kp)
        for img in self.session_state.images:
            if img.name in by_name:
                updated = []
                for kp in by_name[img.name]:
                    kp.image_id = img.id
                    updated.append(kp)
                self.session_state.annotations[img.id] = updated
        emit_annotations_changed(self)
