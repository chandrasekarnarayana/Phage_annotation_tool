"""Annotation mutations and undo/redo helpers."""

from __future__ import annotations

import time
from typing import Iterable, Optional
from phage_annotator.annotation.core import Keypoint
from phage_annotator.session.signal_hub import emit_annotations_changed


class SessionAnnotationsMixin:
    """Mixin for annotation mutations and undo/redo helpers."""

    def _assist_context_for_point(self, image_id: int, point: Keypoint) -> dict[str, object]:
        """Build the local assist context for one committed annotation change."""
        return {
            "image_id": int(image_id),
            "t": int(getattr(point, "t", getattr(self.view_state, "t", 0))),
            "z": int(getattr(point, "z", getattr(self.view_state, "z", 0))),
            "roi_id": str(getattr(point, "roi_name", "") or ""),
            "annotation_space": str(getattr(self.session_state, "annotation_space", "stack")),
        }

    def add_annotation(
        self,
        image_id: int,
        image_name: str,
        t: int,
        z: int,
        y: float,
        x: float,
        label: str,
        scope: str,
        modality_idx: Optional[int] = None,
        annotation_context: str = "",
        source: str = "manual",
        status: str = "active",
        confidence: Optional[float] = None,
        roi_name: str = "",
        notes: str = "",
        meta: Optional[dict] = None,
    ) -> Keypoint:
        """Add an annotation to the session.
        
        Parameters
        ----------
        modality_idx : int, optional
            Index of modality this annotation belongs to.
            If None, annotation is visible on all modalities (backward compatible).
        """
        kp = Keypoint(
            image_id=image_id,
            image_name=image_name,
            t=t if scope == "current" else -1,
            z=z if scope == "current" else -1,
            y=float(y),
            x=float(x),
            label=label,
            source=str(source or "manual"),
            meta=dict(meta or {}),
            modality_idx=modality_idx,
            annotation_context=str(annotation_context or ""),
        )
        kp.status = str(status or "active")
        kp.confidence = confidence
        kp.roi_name = str(roi_name or "")
        kp.notes = str(notes or "")
        kp.meta["annotator"] = self.session_state.current_user
        kp.meta["timestamp"] = time.time()
        self.session_state.annotations.setdefault(image_id, []).append(kp)
        self.session_state.annotations_loaded[image_id] = True
        self._push_undo({"type": "add_point", "point": kp, "image_id": image_id})
        self.set_dirty(True)
        emit_annotations_changed(self, image_id=image_id, change_type="added")
        if hasattr(self, "append_audit_event"):
            self.append_audit_event(
                "annotation_added",
                image_id=image_id,
                annotation_id=kp.annotation_id,
                label=kp.label,
                x=kp.x,
                y=kp.y,
                t=kp.t,
                z=kp.z,
            )
        if hasattr(self, "record_workflow_event"):
            self.record_workflow_event(
                "annotation_added",
                image_id=image_id,
                source=kp.source,
                status=kp.status,
            )
        if hasattr(self, "refresh_provenance_coverage_metrics"):
            self.refresh_provenance_coverage_metrics()
        if hasattr(self, "local_truth_update"):
            context = self._assist_context_for_point(image_id, kp)
            self.local_truth_update(context, kp)
            if hasattr(self, "_queue_local_rescore"):
                self._queue_local_rescore(context)
        
        return kp

    def delete_annotations(
        self, image_id: int, points: Iterable[Keypoint]
    ) -> int:
        """Delete explicit points from an image's annotation list."""

        pts = self.session_state.annotations.get(image_id, [])
        removed = 0
        requested_points = list(points)
        for kp in requested_points:
            try:
                pts.remove(kp)
            except ValueError:
                continue
            self._push_undo({"type": "delete_point", "point": kp, "image_id": image_id})
            removed += 1
        if removed:
            self.set_dirty(True)
            emit_annotations_changed(self, image_id=image_id, change_type="removed")
            if hasattr(self, "append_audit_event"):
                self.append_audit_event(
                    "annotation_deleted",
                    image_id=image_id,
                    count=removed,
                    annotation_ids=[kp.annotation_id for kp in requested_points],
                )
            if hasattr(self, "record_workflow_event"):
                self.record_workflow_event("annotation_deleted", image_id=image_id, count=removed)
            if hasattr(self, "refresh_provenance_coverage_metrics"):
                self.refresh_provenance_coverage_metrics()
            if hasattr(self, "local_truth_update") and requested_points:
                context = self._assist_context_for_point(image_id, requested_points[0])
                for point in requested_points:
                    self.local_truth_update(self._assist_context_for_point(image_id, point), point)
                if hasattr(self, "_queue_local_rescore"):
                    self._queue_local_rescore(context)
        return removed

    def update_annotation(self, image_id: int, old: Keypoint, new: Keypoint) -> bool:
        """Replace a single annotation with an updated version."""
        pts = self.session_state.annotations.get(image_id, [])
        try:
            idx = pts.index(old)
        except ValueError:
            return False
        pts[idx] = new
        self.set_dirty(True)
        emit_annotations_changed(self, image_id=image_id, change_type="modified")
        if hasattr(self, "append_audit_event"):
            self.append_audit_event(
                "annotation_updated",
                image_id=image_id,
                annotation_id=new.annotation_id,
                old_label=old.label,
                new_label=new.label,
            )
        if hasattr(self, "record_workflow_event"):
            self.record_workflow_event(
                "annotation_updated",
                image_id=image_id,
                source=str(getattr(new, "source", "manual")),
                status=str(getattr(new, "status", "active")),
            )
        if hasattr(self, "refresh_provenance_coverage_metrics"):
            self.refresh_provenance_coverage_metrics()
        if hasattr(self, "local_truth_update"):
            self.local_truth_update(self._assist_context_for_point(image_id, old), old)
            self.local_truth_update(self._assist_context_for_point(image_id, new), new)
            if hasattr(self, "_queue_local_rescore"):
                self._queue_local_rescore(self._assist_context_for_point(image_id, new))
        
        return True

    def can_undo(self) -> bool:
        return bool(self._undo_stack)

    def can_redo(self) -> bool:
        return bool(self._redo_stack)

    def _push_undo(self, action: dict) -> None:
        self._undo_stack.append(action)
        self._redo_stack.clear()

    def undo(self) -> bool:
        if not self._undo_stack:
            return False
        action = self._undo_stack.pop()

        if self._is_serialized_command(action):
            from phage_annotator.session.commands import command_from_dict

            cmd = command_from_dict(action, self)
            if cmd and cmd.undo():
                self._redo_stack.append(action)
                return True
            self._undo_stack.append(action)
            return False

        inverse = self._apply_action(action, undo=True)
        if inverse:
            self._redo_stack.append(inverse)
            emit_annotations_changed(self)
            return True
        self._undo_stack.append(action)
        return False

    def redo(self) -> bool:
        if not self._redo_stack:
            return False
        action = self._redo_stack.pop()

        if self._is_serialized_command(action):
            from phage_annotator.session.commands import command_from_dict

            cmd = command_from_dict(action, self)
            if cmd and cmd.redo():
                self._undo_stack.append(action)
                return True
            self._redo_stack.append(action)
            return False

        inverse = self._apply_action(action, undo=False)
        if inverse:
            self._undo_stack.append(inverse)
            emit_annotations_changed(self)
            return True
        self._redo_stack.append(action)
        return False

    def _apply_action(self, action: dict, undo: bool) -> Optional[dict]:
        atype = action.get("type")
        point: Keypoint = action.get("point")
        image_id = action.get("image_id")
        if atype == "add_point":
            if undo:
                self._remove_point(point, image_id)
                return {"type": "delete_point", "point": point, "image_id": image_id}
            self.session_state.annotations.setdefault(image_id, []).append(point)
            return {"type": "add_point", "point": point, "image_id": image_id}
        if atype == "delete_point":
            if undo:
                self.session_state.annotations.setdefault(image_id, []).append(point)
                return {"type": "add_point", "point": point, "image_id": image_id}
            self._remove_point(point, image_id)
            return {"type": "delete_point", "point": point, "image_id": image_id}
        return None

    def _remove_point(self, point: Keypoint, image_id: int) -> None:
        pts = self.session_state.annotations.get(image_id, [])
        try:
            pts.remove(point)
        except ValueError:
            pass

    @staticmethod
    def _is_serialized_command(action: dict) -> bool:
        """Return True when an undo-stack item is a serialized command payload."""
        return bool(
            isinstance(action, dict)
            and action.get("type")
            and action.get("before")
            and action.get("after")
        )
