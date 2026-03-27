"""Annotation context menu actions for near-point editing."""

from __future__ import annotations

from matplotlib.backends.qt_compat import QtCore, QtWidgets

from phage_annotator.core.annotation import Keypoint
from phage_annotator.session.context_commands import (
    DeleteNearestCommand,
    EditNearestMetadataCommand,
    MarkUncertainCommand,
    SnapToLocalMaxCommand,
)
from phage_annotator.ui_qt.dialogs.metadata_editor_dialog import MetadataEditorDialog
from phage_annotator.utils.hit_testing import HitTester


class ContextMenuMixin:
    """Mixin providing right-click context actions for annotations."""

    def _show_annotation_context_menu(
        self,
        x: float,
        y: float,
        global_pos: QtCore.QPoint,
    ) -> None:
        """Show annotation context menu near the clicked coordinate."""
        if not self.images:
            return
        image_id = self.primary_image.id
        all_annotations = self.annotations.get(image_id, [])
        if not all_annotations:
            return

        t_idx = int(self.t_slider.value())
        z_idx = int(self.z_slider.value())
        visible_annotations = [
            ann for ann in all_annotations if ann.t in (t_idx, -1) and ann.z in (z_idx, -1)
        ]
        hit = HitTester.find_nearest(
            visible_annotations,
            x=float(x),
            y=float(y),
            radius=float(getattr(self, "click_radius_px", 20.0)),
        )
        if hit is None:
            return
        target, _ = hit

        menu = QtWidgets.QMenu(self)
        delete_action = menu.addAction("Delete nearest annotation")
        uncertain = bool(target.meta.get("uncertain", False))
        uncertain_action = menu.addAction(
            "Mark as certain" if uncertain else "Mark as uncertain"
        )
        snap_action = menu.addAction("Snap to local maximum")
        menu.addSeparator()
        edit_action = menu.addAction("Edit metadata...")

        selected = menu.exec(global_pos)
        radius = float(getattr(self, "click_radius_px", 20.0))
        if selected is delete_action:
            command = DeleteNearestCommand(self.controller, image_id, x, y, radius=radius)
            self._execute_context_command(command, "Deleted nearest annotation.")
        elif selected is uncertain_action:
            command = MarkUncertainCommand(
                self.controller,
                image_id,
                x,
                y,
                radius=radius,
                uncertain=not uncertain,
            )
            self._execute_context_command(command, "Updated annotation certainty.")
        elif selected is snap_action:
            image_data = self._slice_data(self.primary_image)
            command = SnapToLocalMaxCommand(
                self.controller,
                image_id,
                x,
                y,
                radius=radius,
                search_radius=8.0,
                image_data=image_data,
            )
            self._execute_context_command(command, "Snapped annotation to local maximum.")
        elif selected is edit_action:
            self._edit_annotation_metadata_from_context(target, x=x, y=y, radius=radius)

    def _execute_context_command(self, command, success_message: str) -> bool:
        """Execute an annotation context command through controller history."""
        if not self.controller.execute_view_command(command):
            self._status_warning(
                "No annotation found near click.",
                timeout_ms=2500,
                source="context_menu.execute",
            )
            return False

        self.undo_act.setEnabled(self.controller.can_undo())
        self.redo_act.setEnabled(self.controller.can_redo())
        self._refresh_table()
        self._request_ui_refresh("context-menu", table=True)
        self._update_status()
        self._mark_dirty()
        if hasattr(self, "_schedule_qc_validation"):
            self._schedule_qc_validation(self.primary_image.id)
        self._status_success(
            success_message,
            timeout_ms=2500,
            source="context_menu.execute",
        )
        return True

    def _edit_annotation_metadata_from_context(
        self,
        annotation: Keypoint,
        *,
        x: float,
        y: float,
        radius: float,
    ) -> None:
        """Open metadata editor and apply changes via undoable command."""
        draft = Keypoint(
            image_id=annotation.image_id,
            image_name=annotation.image_name,
            t=annotation.t,
            z=annotation.z,
            y=annotation.y,
            x=annotation.x,
            label=annotation.label,
            annotation_id=annotation.annotation_id,
            image_key=annotation.image_key,
            source=annotation.source,
            meta=dict(annotation.meta),
            modality_idx=annotation.modality_idx,
        )
        dialog = MetadataEditorDialog(draft, parent=self)
        if dialog.exec() != QtWidgets.QDialog.DialogCode.Accepted:
            return

        command = EditNearestMetadataCommand(
            self.controller,
            self.primary_image.id,
            x=x,
            y=y,
            radius=radius,
            annotation_id=annotation.annotation_id,
            new_label=draft.label,
            new_meta=dict(draft.meta),
        )
        self._execute_context_command(command, "Updated annotation metadata.")
