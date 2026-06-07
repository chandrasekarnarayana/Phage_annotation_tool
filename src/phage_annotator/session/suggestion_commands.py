"""Undoable commands for assisted annotation suggestions."""

from __future__ import annotations

from typing import TYPE_CHECKING, Optional

if TYPE_CHECKING:
    from phage_annotator.session.controller import SessionController

from phage_annotator.core.annotation import Keypoint, PointSuggestion
from phage_annotator.session.commands import Command, CommandMemento
from phage_annotator.session.signal_hub import emit_annotations_changed
from phage_annotator.session.suggestion_command_helpers import (
    _history_bucket, _emit_changed, _assist_context_for_suggestion,
    _suggestion_to_dict, _dict_to_suggestion, _suggestion_to_keypoint,
)
from phage_annotator.session.suggestion_commands_batch import AcceptSuggestionsBatchCommand

__all__ = [
    "AcceptSuggestionCommand", "RejectSuggestionCommand",
    "ClearSuggestionsCommand", "AcceptSuggestionsBatchCommand",
]


class AcceptSuggestionCommand(Command):
    """Accept a pending suggestion into committed annotations."""

    def __init__(self, controller: "SessionController", image_id: int, suggestion_id: str):
        """Initialize the object and prepare its runtime state."""
        super().__init__(controller, image_id)
        self.suggestion_id = str(suggestion_id)

    def _find_suggestion(self) -> tuple[Optional[int], Optional[PointSuggestion]]:
        """Find suggestion for the current workflow."""
        suggestions = self.controller.session_state.suggestions.get(self.image_id, [])
        for idx, item in enumerate(suggestions):
            if item.suggestion_id == self.suggestion_id:
                return idx, item
        return None, None

    def execute(self) -> bool:
        """Execute execute for the current workflow."""
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
        """Undo undo for the current workflow."""
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
        """Run the redo workflow."""
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
        """Initialize the object and prepare its runtime state."""
        super().__init__(controller, image_id)
        self.suggestion_id = str(suggestion_id)

    def execute(self) -> bool:
        """Execute execute for the current workflow."""
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
        """Undo undo for the current workflow."""
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
        """Run the redo workflow."""
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
        """Initialize the object and prepare its runtime state."""
        super().__init__(controller, image_id)

    def execute(self) -> bool:
        """Execute execute for the current workflow."""
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
        """Undo undo for the current workflow."""
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
        """Run the redo workflow."""
        if self.memento_after is None:
            return False
        self.controller.session_state.suggestions[self.image_id] = []
        _emit_changed(self.controller, self.image_id)
        return True

    def emit_change_signals(self) -> None:
        """Suggestion commands publish annotation changes internally."""
        return None
