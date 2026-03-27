"""Undoable commands for assisted annotation suggestions."""

from __future__ import annotations

from typing import TYPE_CHECKING, Optional

if TYPE_CHECKING:
    from phage_annotator.session.controller import SessionController

from phage_annotator.core.annotation import Keypoint, PointSuggestion
from phage_annotator.session.commands import Command, CommandMemento
from phage_annotator.session.signal_hub import emit_annotations_changed


def _history_bucket(controller: "SessionController", image_id: int) -> list[PointSuggestion]:
    history = getattr(controller.session_state, "suggestion_history", None)
    if history is None:
        history = {}
        setattr(controller.session_state, "suggestion_history", history)
    return history.setdefault(image_id, [])


def _emit_changed(controller: "SessionController", image_id: int) -> None:
    emit_annotations_changed(controller, image_id=image_id, change_type="modified")
    if hasattr(controller, "append_audit_event"):
        controller.append_audit_event("suggestion_command", image_id=image_id)


def _assist_context_for_suggestion(controller: "SessionController", suggestion: PointSuggestion) -> dict[str, object]:
    """Build a local assist context for post-decision updates."""
    return {
        "image_id": int(getattr(suggestion, "image_id", -1)),
        "t": int(getattr(suggestion, "t", getattr(controller.view_state, "t", 0))),
        "z": int(getattr(suggestion, "z", getattr(controller.view_state, "z", 0))),
        "roi_id": str(getattr(suggestion, "roi_id", "") or ""),
        "annotation_space": str(getattr(controller.session_state, "annotation_space", "stack")),
    }


def _suggestion_to_dict(s: PointSuggestion) -> dict:
    return {
        "image_id": int(s.image_id),
        "image_name": str(s.image_name),
        "t": int(s.t),
        "z": int(s.z),
        "y": float(s.y),
        "x": float(s.x),
        "score": float(s.score),
        "label": str(s.label),
        "suggestion_id": str(s.suggestion_id),
        "source_model": str(s.source_model),
        "source_modality": str(s.source_modality),
        "supporting_modalities": list(getattr(s, "supporting_modalities", []) or []),
        "cross_modality_consistency_score": getattr(s, "cross_modality_consistency_score", None),
        "control_contradiction_score": getattr(s, "control_contradiction_score", None),
        "scale_sigma": float(s.scale_sigma),
        "psf_radius": float(s.psf_radius),
        "roi_id": s.roi_id,
        "uncertainty_score": getattr(s, "uncertainty_score", None),
        "uncertainty_reason": str(getattr(s, "uncertainty_reason", "") or ""),
        "density_context": dict(getattr(s, "density_context", {}) or {}),
        "score_components": dict(s.score_components),
        "status": str(s.status),
        "meta": dict(s.meta),
    }


def _dict_to_suggestion(data: dict) -> PointSuggestion:
    return PointSuggestion(
        image_id=int(data.get("image_id", -1)),
        image_name=str(data.get("image_name", "")),
        t=int(data.get("t", -1)),
        z=int(data.get("z", -1)),
        y=float(data.get("y", 0.0)),
        x=float(data.get("x", 0.0)),
        score=float(data.get("score", data.get("confidence", 0.0))),
        label=str(data.get("label", "phage")),
        suggestion_id=str(data.get("suggestion_id", "")),
        source_model=str(data.get("source_model", "unknown")),
        source_modality=str(data.get("source_modality", "raw")),
        supporting_modalities=list(data.get("supporting_modalities", []) or []),
        cross_modality_consistency_score=data.get("cross_modality_consistency_score"),
        control_contradiction_score=data.get("control_contradiction_score"),
        scale_sigma=float(data.get("scale_sigma", 1.0)),
        psf_radius=float(data.get("psf_radius", 6.0)),
        roi_id=data.get("roi_id"),
        uncertainty_score=data.get("uncertainty_score"),
        uncertainty_reason=str(data.get("uncertainty_reason", "") or ""),
        density_context=dict(data.get("density_context", {}) or {}),
        score_components=dict(data.get("score_components", {})),
        status=str(data.get("status", "proposed")),
        meta=dict(data.get("meta", {})),
    )


def _suggestion_to_keypoint(s: PointSuggestion) -> Keypoint:
    kp = Keypoint(
        image_id=int(s.image_id),
        image_name=str(s.image_name),
        t=int(s.t),
        z=int(s.z),
        y=float(s.y),
        x=float(s.x),
        label=str(s.label),
        source=f"suggested:{s.source_model}",
        meta={
            "proposal_score": float(s.score),
            "score": float(s.score),
            "suggestion_id": s.suggestion_id,
            "source_model": str(s.source_model),
            "source_modality": str(s.source_modality),
            "candidate_class": str(dict(getattr(s, "meta", {}) or {}).get("candidate_class", "new")),
            "uncertainty_score": float(getattr(s, "uncertainty_score", 0.0) or 0.0),
            "uncertainty_reason": str(getattr(s, "uncertainty_reason", "") or ""),
            "supporting_modalities": list(getattr(s, "supporting_modalities", []) or []),
            "cross_modality_consistency_score": getattr(s, "cross_modality_consistency_score", None),
            "control_contradiction_score": getattr(s, "control_contradiction_score", None),
            "density_context": dict(getattr(s, "density_context", {}) or {}),
        },
    )
    kp.status = "accepted"
    kp.confidence = float(dict(getattr(s, "meta", {}) or {}).get("p_accept", s.score))
    kp.roi_name = str(getattr(s, "roi_id", "") or "")
    kp.notes = str(dict(getattr(s, "meta", {}) or {}).get("notes", "") or "")
    return kp


class AcceptSuggestionCommand(Command):
    """Accept a pending suggestion into committed annotations."""

    def __init__(self, controller: "SessionController", image_id: int, suggestion_id: str):
        super().__init__(controller, image_id)
        self.suggestion_id = str(suggestion_id)

    def _find_suggestion(self) -> tuple[Optional[int], Optional[PointSuggestion]]:
        suggestions = self.controller.session_state.suggestions.get(self.image_id, [])
        for idx, item in enumerate(suggestions):
            if item.suggestion_id == self.suggestion_id:
                return idx, item
        return None, None

    def execute(self) -> bool:
        idx, suggestion = self._find_suggestion()
        if idx is None or suggestion is None:
            return False

        keypoint = _suggestion_to_keypoint(suggestion)
        self.controller.session_state.annotations.setdefault(self.image_id, []).append(keypoint)
        self.controller.session_state.suggestions[self.image_id].pop(idx)

        self.memento_before = CommandMemento(
            command_type="accept_suggestion",
            image_id=self.image_id,
            data={
                "suggestion": _suggestion_to_dict(suggestion),
                "suggestion_index": int(idx),
                "annotation_id": keypoint.annotation_id,
            },
        )
        self.memento_after = CommandMemento(
            command_type="accept_suggestion",
            image_id=self.image_id,
            data={
                "annotation_id": keypoint.annotation_id,
                "suggestion_id": suggestion.suggestion_id,
            },
        )
        suggestion.status = "accepted"
        _history_bucket(self.controller, self.image_id).append(suggestion)

        if hasattr(self.controller, "update_suggestion_metrics"):
            self.controller.update_suggestion_metrics(accepted=1)
        if hasattr(self.controller, "local_truth_update"):
            context = _assist_context_for_suggestion(self.controller, suggestion)
            self.controller.local_truth_update(context, keypoint)
            if hasattr(self.controller, "_queue_local_rescore"):
                self.controller._queue_local_rescore(context)
        if hasattr(self.controller, "observe_suggestion_feedback"):
            self.controller.observe_suggestion_feedback(suggestion, accepted=True)
        _emit_changed(self.controller, self.image_id)
        return True

    def undo(self) -> bool:
        if self.memento_before is None:
            return False
        annotation_id = self.memento_before.data.get("annotation_id")
        snapshot = self.memento_before.data.get("suggestion")
        index = int(self.memento_before.data.get("suggestion_index", -1))
        if not isinstance(annotation_id, str) or not isinstance(snapshot, dict):
            return False

        anns = self.controller.session_state.annotations.get(self.image_id, [])
        remove_idx = None
        for idx, ann in enumerate(anns):
            if ann.annotation_id == annotation_id:
                remove_idx = idx
                break
        if remove_idx is None:
            return False
        anns.pop(remove_idx)

        suggestions = self.controller.session_state.suggestions.setdefault(self.image_id, [])
        restored = _dict_to_suggestion(snapshot)
        if index < 0 or index > len(suggestions):
            suggestions.append(restored)
        else:
            suggestions.insert(index, restored)
        if hasattr(self.controller, "local_truth_update"):
            context = _assist_context_for_suggestion(self.controller, restored)
            self.controller.local_truth_update(context, restored)
            if hasattr(self.controller, "_queue_local_rescore"):
                self.controller._queue_local_rescore(context)
        _emit_changed(self.controller, self.image_id)
        return True

    def redo(self) -> bool:
        if self.memento_after is None:
            return False
        sid = self.memento_after.data.get("suggestion_id")
        if not isinstance(sid, str):
            return False
        self.suggestion_id = sid
        return self.execute()

    def emit_change_signals(self) -> None:
        """Suggestion commands publish annotation changes internally."""
        return None


class RejectSuggestionCommand(Command):
    """Reject and remove one pending suggestion."""

    def __init__(self, controller: "SessionController", image_id: int, suggestion_id: str):
        super().__init__(controller, image_id)
        self.suggestion_id = str(suggestion_id)

    def execute(self) -> bool:
        suggestions = self.controller.session_state.suggestions.get(self.image_id, [])
        for idx, item in enumerate(suggestions):
            if item.suggestion_id != self.suggestion_id:
                continue
            self.memento_before = CommandMemento(
                command_type="reject_suggestion",
                image_id=self.image_id,
                data={
                    "suggestion": _suggestion_to_dict(item),
                    "suggestion_index": int(idx),
                },
            )
            suggestions.pop(idx)
            item.status = "rejected"
            _history_bucket(self.controller, self.image_id).append(item)
            self.memento_after = CommandMemento(
                command_type="reject_suggestion",
                image_id=self.image_id,
                data={"suggestion_id": self.suggestion_id},
            )
            if hasattr(self.controller, "update_suggestion_metrics"):
                self.controller.update_suggestion_metrics(rejected=1)
            if hasattr(self.controller, "local_truth_update"):
                context = _assist_context_for_suggestion(self.controller, item)
                self.controller.local_truth_update(context, item)
                if hasattr(self.controller, "_queue_local_rescore"):
                    self.controller._queue_local_rescore(context)
            if hasattr(self.controller, "observe_suggestion_feedback"):
                self.controller.observe_suggestion_feedback(item, accepted=False)
            _emit_changed(self.controller, self.image_id)
            return True
        return False

    def undo(self) -> bool:
        if self.memento_before is None:
            return False
        snapshot = self.memento_before.data.get("suggestion")
        index = int(self.memento_before.data.get("suggestion_index", -1))
        if not isinstance(snapshot, dict):
            return False
        suggestions = self.controller.session_state.suggestions.setdefault(self.image_id, [])
        restored = _dict_to_suggestion(snapshot)
        if index < 0 or index > len(suggestions):
            suggestions.append(restored)
        else:
            suggestions.insert(index, restored)
        if hasattr(self.controller, "local_truth_update"):
            context = _assist_context_for_suggestion(self.controller, restored)
            self.controller.local_truth_update(context, restored)
            if hasattr(self.controller, "_queue_local_rescore"):
                self.controller._queue_local_rescore(context)
        _emit_changed(self.controller, self.image_id)
        return True

    def redo(self) -> bool:
        if self.memento_after is None:
            return False
        sid = self.memento_after.data.get("suggestion_id")
        if not isinstance(sid, str):
            return False
        self.suggestion_id = sid
        return self.execute()

    def emit_change_signals(self) -> None:
        """Suggestion commands publish annotation changes internally."""
        return None


class ClearSuggestionsCommand(Command):
    """Clear pending suggestions for one image."""

    def __init__(self, controller: "SessionController", image_id: int):
        super().__init__(controller, image_id)

    def execute(self) -> bool:
        suggestions = list(self.controller.session_state.suggestions.get(self.image_id, []))
        if not suggestions:
            return False
        for suggestion in suggestions:
            suggestion.status = "cleared"
        _history_bucket(self.controller, self.image_id).extend(suggestions)
        self.memento_before = CommandMemento(
            command_type="clear_suggestions",
            image_id=self.image_id,
            data={"suggestions": [_suggestion_to_dict(s) for s in suggestions]},
        )
        self.controller.session_state.suggestions[self.image_id] = []
        self.memento_after = CommandMemento(
            command_type="clear_suggestions",
            image_id=self.image_id,
            data={"count": len(suggestions)},
        )
        _emit_changed(self.controller, self.image_id)
        return True

    def undo(self) -> bool:
        if self.memento_before is None:
            return False
        rows = self.memento_before.data.get("suggestions", [])
        if not isinstance(rows, list):
            return False
        self.controller.session_state.suggestions[self.image_id] = [
            _dict_to_suggestion(row) for row in rows if isinstance(row, dict)
        ]
        _emit_changed(self.controller, self.image_id)
        return True

    def redo(self) -> bool:
        if self.memento_after is None:
            return False
        self.controller.session_state.suggestions[self.image_id] = []
        _emit_changed(self.controller, self.image_id)
        return True

    def emit_change_signals(self) -> None:
        """Suggestion commands publish annotation changes internally."""
        return None


class AcceptSuggestionsBatchCommand(Command):
    """Accept multiple suggestions as a single undoable batch operation."""

    def __init__(self, controller: "SessionController", image_id: int, suggestion_ids: list[str]):
        super().__init__(controller, image_id)
        self.suggestion_ids = [str(sid) for sid in suggestion_ids if str(sid)]

    def execute(self) -> bool:
        suggestions = self.controller.session_state.suggestions.get(self.image_id, [])
        if not suggestions or not self.suggestion_ids:
            return False
        id_set = set(self.suggestion_ids)
        selected = [(idx, s) for idx, s in enumerate(suggestions) if s.suggestion_id in id_set]
        if not selected:
            return False

        annotations = self.controller.session_state.annotations.setdefault(self.image_id, [])
        rows = []
        removed_indices = []
        for idx, suggestion in selected:
            kp = _suggestion_to_keypoint(suggestion)
            annotations.append(kp)
            rows.append(
                {
                    "suggestion": _suggestion_to_dict(suggestion),
                    "suggestion_index": int(idx),
                    "annotation_id": kp.annotation_id,
                }
            )
            suggestion.status = "accepted"
            _history_bucket(self.controller, self.image_id).append(suggestion)
            removed_indices.append(int(idx))
            if hasattr(self.controller, "local_truth_update"):
                context = _assist_context_for_suggestion(self.controller, suggestion)
                self.controller.local_truth_update(context, kp)
            if hasattr(self.controller, "observe_suggestion_feedback"):
                self.controller.observe_suggestion_feedback(suggestion, accepted=True)

        for idx in sorted(removed_indices, reverse=True):
            self.controller.session_state.suggestions[self.image_id].pop(idx)

        self.memento_before = CommandMemento(
            command_type="accept_suggestions_batch",
            image_id=self.image_id,
            data={"rows": rows},
        )
        self.memento_after = CommandMemento(
            command_type="accept_suggestions_batch",
            image_id=self.image_id,
            data={"count": len(rows)},
        )
        if hasattr(self.controller, "update_suggestion_metrics"):
            self.controller.update_suggestion_metrics(accepted=len(rows))
        if rows and hasattr(self.controller, "_queue_local_rescore"):
            first = rows[0].get("suggestion")
            if isinstance(first, dict):
                self.controller._queue_local_rescore(
                    _assist_context_for_suggestion(self.controller, _dict_to_suggestion(first))
                )
        _emit_changed(self.controller, self.image_id)
        return True

    def undo(self) -> bool:
        if self.memento_before is None:
            return False
        rows = self.memento_before.data.get("rows", [])
        if not isinstance(rows, list):
            return False
        remove_ids = {str(r.get("annotation_id", "")) for r in rows if isinstance(r, dict)}
        anns = self.controller.session_state.annotations.get(self.image_id, [])
        self.controller.session_state.annotations[self.image_id] = [
            ann for ann in anns if str(getattr(ann, "annotation_id", "")) not in remove_ids
        ]
        suggestions = self.controller.session_state.suggestions.setdefault(self.image_id, [])
        restore_rows = []
        for row in rows:
            if not isinstance(row, dict):
                continue
            snap = row.get("suggestion")
            if not isinstance(snap, dict):
                continue
            restore_rows.append((int(row.get("suggestion_index", len(suggestions))), _dict_to_suggestion(snap)))
        for idx, suggestion in sorted(restore_rows, key=lambda x: x[0]):
            if idx < 0 or idx > len(suggestions):
                suggestions.append(suggestion)
            else:
                suggestions.insert(idx, suggestion)
        if restore_rows and hasattr(self.controller, "local_truth_update"):
            self.controller.local_truth_update(
                _assist_context_for_suggestion(self.controller, restore_rows[0][1]),
                restore_rows[0][1],
            )
            if hasattr(self.controller, "_queue_local_rescore"):
                self.controller._queue_local_rescore(
                    _assist_context_for_suggestion(self.controller, restore_rows[0][1])
                )
        _emit_changed(self.controller, self.image_id)
        return True

    def redo(self) -> bool:
        return self.execute()

    def emit_change_signals(self) -> None:
        """Suggestion commands publish annotation changes internally."""
        return None
