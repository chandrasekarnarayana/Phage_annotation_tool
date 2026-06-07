"""Batch accept command for assisted annotation suggestions."""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from phage_annotator.session.controller import SessionController

from phage_annotator.core.annotation import Keypoint, PointSuggestion
from phage_annotator.session.commands import Command, CommandMemento
from phage_annotator.session.signal_hub import emit_annotations_changed
from phage_annotator.session.suggestion_command_helpers import (
    _history_bucket, _emit_changed, _assist_context_for_suggestion,
    _suggestion_to_dict, _dict_to_suggestion, _suggestion_to_keypoint,
)

class AcceptSuggestionsBatchCommand(Command):
    """Accept multiple suggestions as a single undoable batch operation."""

    def __init__(self, controller: "SessionController", image_id: int, suggestion_ids: list[str]):
        """Initialize the object and prepare its runtime state."""
        super().__init__(controller, image_id)
        self.suggestion_ids = [str(sid) for sid in suggestion_ids if str(sid)]

    def execute(self) -> bool:
        """Execute execute for the current workflow."""
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
        """Undo undo for the current workflow."""
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
        """Run the redo workflow."""
        return self.execute()

    def emit_change_signals(self) -> None:
        """Suggestion commands publish annotation changes internally."""
        return None
