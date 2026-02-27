"""Annotation mutations and undo/redo helpers."""

from __future__ import annotations

from typing import Iterable, Optional
from phage_annotator.annotation.core import Keypoint
from phage_annotator.framework import get_event_service
from phage_annotator.framework.events import AnnotationChangedEvent, CacheInvalidationEvent


class SessionAnnotationsMixin:
    """Mixin for annotation mutations and undo/redo helpers."""

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
            modality_idx=modality_idx,
        )
        self.session_state.annotations.setdefault(image_id, []).append(kp)
        self.session_state.annotations_loaded[image_id] = True
        self._push_undo({"type": "add_point", "point": kp, "image_id": image_id})
        self.set_dirty(True)
        self.annotations_changed.emit()
        
        # Publish event for service integration
        try:
            event_service = get_event_service()
            event_service.publish(
                AnnotationChangedEvent(
                    image_id=image_id,
                    annotations=self.session_state.annotations.get(image_id, []),
                    change_type="added"
                )
            )
            # Invalidate caches
            event_service.publish(CacheInvalidationEvent(scope="image", image_id=image_id))
        except Exception:
            pass  # Gracefully handle if event service not initialized
        
        return kp

    def delete_annotations(
        self, image_id: int, points: Iterable[Keypoint]
    ) -> int:
        """Delete explicit points from an image's annotation list."""

        pts = self.session_state.annotations.get(image_id, [])
        removed = 0
        for kp in list(points):
            try:
                pts.remove(kp)
            except ValueError:
                continue
            self._push_undo({"type": "delete_point", "point": kp, "image_id": image_id})
            removed += 1
        if removed:
            self.set_dirty(True)
            self.annotations_changed.emit()            
            # Publish event for service integration
            try:
                event_service = get_event_service()
                event_service.publish(
                    AnnotationChangedEvent(
                        image_id=image_id,
                        annotations=self.session_state.annotations.get(image_id, []),
                        change_type="removed"
                    )
                )
                event_service.publish(CacheInvalidationEvent(scope="image", image_id=image_id))
            except Exception:
                pass  # Gracefully handle if event service not initialized
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
        self.annotations_changed.emit()
        
        # Publish event for service integration
        try:
            event_service = get_event_service()
            event_service.publish(
                AnnotationChangedEvent(
                    image_id=image_id,
                    annotations=self.session_state.annotations.get(image_id, []),
                    change_type="modified"
                )
            )
            event_service.publish(CacheInvalidationEvent(scope="image", image_id=image_id))
        except Exception:
            pass  # Gracefully handle if event service not initialized
        
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
            self.annotations_changed.emit()
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
            self.annotations_changed.emit()
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
