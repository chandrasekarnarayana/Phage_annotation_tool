"""Assist generation and batch suggestion workflow helpers."""

from __future__ import annotations

import os
import time
from typing import List, Optional

from matplotlib.backends.qt_compat import QtCore, QtWidgets

from phage_annotator.core.annotation import PointSuggestion
from phage_annotator.session.suggestion_commands import (
    AcceptSuggestionCommand,
    AcceptSuggestionsBatchCommand,
    ClearSuggestionsCommand,
    RejectSuggestionCommand,
)


def _set_generation_progress(
    owner,
    *,
    running: bool,
    text: str,
    progress_value: int | None = None,
) -> None:
    """Update assist queue generation state without blocking the GUI."""
    owner._assist_generation_running = bool(running)
    owner._assist_generation_message = str(text)
    owner._assist_generation_progress = None if progress_value is None else int(progress_value)
    panel = getattr(owner, "review_queue_panel", None)
    if panel is None:
        return
    panel.suggest_btn.setEnabled(not running)
    if running:
        panel.progress_lbl.setText(str(text))
        if progress_value is None:
            panel.progress_bar.setRange(0, 0)
        else:
            panel.progress_bar.setRange(0, 100)
            panel.progress_bar.setValue(max(0, min(100, int(progress_value))))
    else:
        panel.progress_bar.setRange(0, 100)


def suggest_points_current_slice(owner) -> None:
    """Generate ranked suggestions for the active T/Z slice."""
    image = owner.primary_image
    image_id = image.id
    t_idx = int(owner.t_slider.value())
    z_idx = int(owner.z_slider.value())
    strategy = str(getattr(owner, "_suggestion_strategy", "current_view"))
    label = str(owner.current_label)
    if owner._slice_data(image) is None:
        return
    _set_generation_progress(
        owner,
        running=True,
        text=f"Generating suggestions for slice T={t_idx}, Z={z_idx}...",
        progress_value=None,
    )

    def _worker(progress, cancel):
        if cancel.is_cancelled():
            return None
        progress(15, "Finding candidates")
        image_data = owner._slice_data(image)
        generated = owner._gating_strategy_candidates(
            image=image,
            t_idx=t_idx,
            z_idx=z_idx,
            strategy=strategy,
            label=label,
        )
        if cancel.is_cancelled():
            return None
        progress(70, "Ranking suggestions")
        generated = owner._rank_and_calibrate_suggestions(generated)
        owner._enrich_suggestions_for_training(generated, image_data)
        progress(100, "Finalizing")
        return generated

    def _on_progress(value, message):
        _set_generation_progress(
            owner,
            running=True,
            text=f"Generating suggestions: {message}" if message else "Generating suggestions...",
            progress_value=value,
        )

    def _on_result(generated):
        _set_generation_progress(owner, running=False, text="Progress: 0 / 0", progress_value=0)
        if generated is None:
            return
        generated_at = float(time.time())
        for suggestion in generated:
            suggestion.meta["generated_at_ts"] = generated_at
        summary = owner.controller.append_generated_suggestions(image_id, generated, sort_pending=True)
        owner.controller.update_suggestion_metrics(generated=int(summary.get("input_count", len(generated))))
        owner.controller.append_audit_event(
            "suggestions_generated",
            image_id=image_id,
            model=getattr(getattr(owner, "_suggestion_model", None), "model_name", "unknown"),
            count=len(generated),
            strategy=strategy,
        )
        owner._remember_generation_context(generated)
        ctx_key = owner.controller._context_key(
            suggestion=(
                generated[0]
                if generated
                else PointSuggestion(image_id, image.name, t_idx, z_idx, 0, 0, 0.0)
            ),
            annotation_space=str(getattr(owner.controller.session_state, "annotation_space", "stack")),
        )
        _, assist_txt = owner.controller.assist_status(
            annotation_space=str(getattr(owner.controller.session_state, "annotation_space", "stack")),
            context_key=ctx_key,
        )
        owner._suggestion_cursor = 0
        owner._request_ui_refresh("standard-actions")
        owner._status_success(
            "Generated "
            f"{int(summary.get('input_count', len(generated)))} candidate(s): "
            f"{int(summary.get('new_count', 0))} new, "
            f"{int(summary.get('near_count', 0))} near existing, "
            f"{int(summary.get('conflict_count', 0))} conflict, "
            f"{int(summary.get('duplicate_count', 0))} duplicate skipped. "
            f"{assist_txt}",
            source="assist.generate.slice",
        )
        owner._refresh_assist_warmup_panel()

    def _on_error(err: str) -> None:
        _set_generation_progress(owner, running=False, text="Progress: 0 / 0", progress_value=0)
        owner._append_log(f"[Assist] Suggest slice error\n{err}")
        owner._status_error(
            "Suggestion generation failed (see Logs).",
            timeout_ms=5000,
            source="assist.generate.slice",
        )

    owner.jobs.submit(
        _worker,
        name="Generate suggestions (current slice)",
        on_result=_on_result,
        on_error=_on_error,
        on_progress=_on_progress,
        priority="interactive",
        replace_key=f"suggest-slice-{image_id}",
    )


def suggest_points_current_image(owner) -> None:
    """Generate ranked suggestions for every T/Z slice in the current image."""
    image = owner.primary_image
    if image.array is None:
        return
    image_id = image.id
    total = 0
    queued_total = 0
    duplicate_total = 0
    near_total = 0
    conflict_total = 0
    new_total = 0
    t_size = int(image.array.shape[0])
    z_size = int(image.array.shape[1])
    generation_space = str(
        getattr(owner.controller.session_state, "generation_space", "stack")
    ).strip().lower()
    z_indices = [0] if generation_space == "projection" else list(range(z_size))
    strategy = str(getattr(owner, "_suggestion_strategy", "current_view"))
    label = str(owner.current_label)
    _set_generation_progress(
        owner,
        running=True,
        text="Generating suggestions for the full image...",
        progress_value=0,
    )

    def _worker(progress, cancel):
        all_generated = []
        total_steps = max(1, t_size * len(z_indices))
        completed = 0
        for t_idx in range(t_size):
            for z_idx in z_indices:
                if cancel.is_cancelled():
                    return None
                slice_data = owner._slice_data(image, t_override=t_idx, z_override=z_idx)
                generated = owner._gating_strategy_candidates(
                    image=image,
                    t_idx=t_idx,
                    z_idx=z_idx,
                    strategy=strategy,
                    label=label,
                )
                generated = owner._rank_and_calibrate_suggestions(generated)
                owner._enrich_suggestions_for_training(generated, slice_data)
                all_generated.extend(generated)
                completed += 1
                progress(
                    int(round(100.0 * float(completed) / float(total_steps))),
                    f"Slice {completed}/{total_steps}",
                )
        return all_generated

    def _on_progress(value, message):
        _set_generation_progress(
            owner,
            running=True,
            text=f"Generating suggestions: {message}" if message else "Generating suggestions...",
            progress_value=value,
        )

    def _on_result(all_generated):
        nonlocal total, queued_total, duplicate_total, near_total, conflict_total, new_total
        _set_generation_progress(owner, running=False, text="Progress: 0 / 0", progress_value=0)
        if all_generated is None:
            return
        generated_at = float(time.time())
        for suggestion in all_generated:
            suggestion.meta["generated_at_ts"] = generated_at
        summary = owner.controller.append_generated_suggestions(image_id, all_generated, sort_pending=False)
        total = int(summary.get("input_count", len(all_generated)))
        queued_total = int(summary.get("queued_count", 0))
        duplicate_total = int(summary.get("duplicate_count", 0))
        near_total = int(summary.get("near_count", 0))
        conflict_total = int(summary.get("conflict_count", 0))
        new_total = int(summary.get("new_count", 0))
        owner.controller.sort_pending_suggestions(image_id)
        owner.controller.update_suggestion_metrics(generated=total)
        owner.controller.append_audit_event(
            "suggestions_generated",
            image_id=image_id,
            model=getattr(getattr(owner, "_suggestion_model", None), "model_name", "unknown"),
            count=total,
            scope="all_slices",
            strategy=strategy,
        )
        owner._remember_generation_context(owner.suggestions.get(image_id, []))
        owner._suggestion_cursor = 0
        owner._request_ui_refresh("standard-actions")
        owner._status_success(
            "Generated "
            f"{total} candidate(s) for full image: "
            f"{new_total} new, {near_total} near existing, "
            f"{conflict_total} conflict, {duplicate_total} duplicate skipped, "
            f"{queued_total} queued for review.",
            source="assist.generate.image",
        )
        owner._refresh_assist_warmup_panel()

    def _on_error(err: str) -> None:
        _set_generation_progress(owner, running=False, text="Progress: 0 / 0", progress_value=0)
        owner._append_log(f"[Assist] Suggest image error\n{err}")
        owner._status_error(
            "Full-image suggestion generation failed (see Logs).",
            timeout_ms=5000,
            source="assist.generate.image",
        )

    owner.jobs.submit(
        _worker,
        name="Generate suggestions (full image)",
        on_result=_on_result,
        on_error=_on_error,
        on_progress=_on_progress,
        priority="interactive",
        replace_key=f"suggest-image-{image_id}",
    )


def preview_batch_accept_dialog(
    owner,
    *,
    candidates: List[PointSuggestion],
    title: str,
    description: str,
    stale_override_required: bool = False,
) -> Optional[List[str]]:
    """Show the suggestion preflight dialog and return accepted IDs."""
    if not candidates:
        return []
    if stale_override_required and os.environ.get("QT_QPA_PLATFORM", "").lower() == "offscreen":
        owner._status_warning(
            "Batch blocked: stale suggestions require one-shot override confirmation.",
            timeout_ms=5000,
            source="assist.batch.preview",
        )
        return []
    dialog = QtWidgets.QDialog(owner)
    dialog.setWindowTitle(str(title))
    layout = QtWidgets.QVBoxLayout(dialog)
    layout.addWidget(QtWidgets.QLabel(str(description)))
    stale_chk = None
    if stale_override_required:
        warn = QtWidgets.QLabel(
            "Stale detected: annotations changed after suggestion generation.\n"
            "Regenerate is recommended. To proceed once, acknowledge below."
        )
        warn.setStyleSheet("color: #d84315; font-weight: 600;")
        warn.setWordWrap(True)
        layout.addWidget(warn)
        stale_chk = QtWidgets.QCheckBox("Accept stale suggestions for this batch only")
        stale_chk.setChecked(False)
        layout.addWidget(stale_chk)
    table = QtWidgets.QTableWidget(len(candidates), 5, dialog)
    table.setHorizontalHeaderLabels(
        ["Use", "x", "y", "generator score", "Acceptance likelihood (p_accept)"]
    )
    for row, suggestion in enumerate(candidates):
        use_item = QtWidgets.QTableWidgetItem()
        use_item.setFlags(use_item.flags() | QtCore.Qt.ItemFlag.ItemIsUserCheckable)
        use_item.setCheckState(QtCore.Qt.CheckState.Checked)
        table.setItem(row, 0, use_item)
        table.setItem(row, 1, QtWidgets.QTableWidgetItem(str(int(round(float(suggestion.x))))))
        table.setItem(row, 2, QtWidgets.QTableWidgetItem(str(int(round(float(suggestion.y))))))
        table.setItem(row, 3, QtWidgets.QTableWidgetItem(f"{float(suggestion.score):.2f}"))
        p_accept = float(dict(getattr(suggestion, "meta", {}) or {}).get("p_accept", 0.0))
        conf_avail = bool(dict(getattr(suggestion, "meta", {}) or {}).get("confidence_available", False))
        p_text = f"{p_accept:.2f}" if conf_avail else "heuristic"
        table.setItem(row, 4, QtWidgets.QTableWidgetItem(p_text))
    table.resizeColumnsToContents()
    layout.addWidget(table)
    buttons = QtWidgets.QDialogButtonBox(
        QtWidgets.QDialogButtonBox.Ok | QtWidgets.QDialogButtonBox.Cancel,
        parent=dialog,
    )
    layout.addWidget(buttons)
    buttons.accepted.connect(dialog.accept)
    buttons.rejected.connect(dialog.reject)
    if dialog.exec() != QtWidgets.QDialog.DialogCode.Accepted:
        return None
    if stale_override_required and (stale_chk is None or not stale_chk.isChecked()):
        owner._status_warning(
            "Batch blocked: stale suggestions require one-shot override confirmation.",
            timeout_ms=5000,
            source="assist.batch.preview",
        )
        return []
    selected_ids: List[str] = []
    for row, suggestion in enumerate(candidates):
        item = table.item(row, 0)
        if item is not None and item.checkState() == QtCore.Qt.CheckState.Checked:
            selected_ids.append(str(suggestion.suggestion_id))
    return selected_ids


def accept_visible_suggestions(owner) -> None:
    """Accept visible suggestions as one undoable batch."""
    if not owner._ensure_annotation_write_context_confirmed("Accept suggestions"):
        return
    visible = owner._visible_suggestions()
    if not visible:
        owner._status_info("No visible suggestions to accept.", source="assist.accept.visible")
        return
    freshness = owner._suggestion_freshness_state(owner.primary_image.id, visible)
    selected_ids = preview_batch_accept_dialog(
        owner,
        candidates=list(visible),
        title="Preview Batch Accept (Visible Suggestions)",
        description=(
            "Select visible suggestions to accept. "
            "This will be applied as one batch undo step."
        ),
        stale_override_required=bool(
            bool(getattr(owner, "_disable_bulk_accept_when_stale", True))
            and freshness.get("is_stale", False)
        ),
    )
    if selected_ids is None:
        owner._status_info("Batch accept cancelled.", source="assist.accept.visible")
        return
    if not selected_ids:
        owner._status_info(
            "Batch accept cancelled (no suggestions selected).",
            source="assist.accept.visible",
        )
        return
    cmd = AcceptSuggestionsBatchCommand(owner.controller, owner.primary_image.id, selected_ids)
    accepted = 0
    if owner.controller.execute_view_command(cmd):
        accepted = len(selected_ids)
        owner.controller.update_suggestion_metrics(correction_distance=0.0)
        if getattr(owner, "_interactive_learning_enabled", lambda: False)():
            for suggestion in visible:
                if suggestion.suggestion_id in selected_ids:
                    owner._interactive_learning_model.add_example(suggestion, accepted=True)
        if bool(getattr(owner, "_timed_session_active", False)):
            owner._timed_session_accepts = int(getattr(owner, "_timed_session_accepts", 0)) + accepted
            owner._timed_session_points = int(getattr(owner, "_timed_session_points", 0)) + accepted
    owner.undo_act.setEnabled(owner.controller.can_undo())
    owner.redo_act.setEnabled(owner.controller.can_redo())
    if accepted:
        owner._note_annotation_edit(owner.primary_image.id)
        owner._refresh_table()
        owner._request_ui_refresh("standard-actions")
        owner._schedule_qc_validation(owner.primary_image.id)
    owner._status_success(f"Accepted {accepted} suggestion(s).", source="assist.accept.visible")
    owner._refresh_assist_warmup_panel()


def accept_high_confidence_suggestions(owner) -> None:
    """Accept visible high-confidence suggestions."""
    if not owner._ensure_annotation_write_context_confirmed("Accept high-confidence suggestions"):
        return
    visible = owner._visible_suggestions()
    candidates = [
        s
        for s in visible
        if bool(dict(getattr(s, "meta", {}) or {}).get("confidence_available", False))
        and float(dict(getattr(s, "meta", {}) or {}).get("p_accept", 0.0)) >= 0.75
    ]
    if not candidates:
        owner._status_info(
            "No high-confidence suggestions to accept.",
            source="assist.accept.high_confidence",
        )
        return
    freshness = owner._suggestion_freshness_state(owner.primary_image.id, visible)
    selected_ids = preview_batch_accept_dialog(
        owner,
        candidates=candidates,
        title="Preview Batch Accept (Green Suggestions)",
        description=(
            "Select high-confidence suggestions to accept. "
            "This will be applied as one batch undo step."
        ),
        stale_override_required=bool(
            bool(getattr(owner, "_disable_bulk_accept_when_stale", True))
            and freshness.get("is_stale", False)
        ),
    )
    if selected_ids is None:
        owner._status_info("Batch accept cancelled.", source="assist.accept.high_confidence")
        return
    if not selected_ids:
        owner._status_info(
            "Batch accept cancelled (no suggestions selected).",
            source="assist.accept.high_confidence",
        )
        return
    cmd = AcceptSuggestionsBatchCommand(owner.controller, owner.primary_image.id, selected_ids)
    accepted = 0
    if owner.controller.execute_view_command(cmd):
        accepted = len(selected_ids)
        owner.controller.update_suggestion_metrics(correction_distance=0.0)
        if getattr(owner, "_interactive_learning_enabled", lambda: False)():
            for suggestion in candidates:
                if suggestion.suggestion_id in selected_ids:
                    owner._interactive_learning_model.add_example(suggestion, accepted=True)
    owner.undo_act.setEnabled(owner.controller.can_undo())
    owner.redo_act.setEnabled(owner.controller.can_redo())
    if accepted:
        owner._note_annotation_edit(owner.primary_image.id)
        owner._refresh_table()
        owner._request_ui_refresh("standard-actions")
        owner._schedule_qc_validation(owner.primary_image.id)
    owner._status_success(
        f"Accepted {accepted} high-confidence suggestion(s).",
        source="assist.accept.high_confidence",
    )
    owner._refresh_assist_warmup_panel()


def reject_visible_suggestions(owner) -> None:
    """Reject all visible suggestions."""
    visible = owner._visible_suggestions()
    reason_key = "unspecified"
    rejected = 0
    for suggestion in list(visible):
        cmd = RejectSuggestionCommand(owner.controller, owner.primary_image.id, suggestion.suggestion_id)
        if owner.controller.execute_view_command(cmd):
            rejected += 1
            owner.controller.update_suggestion_metrics(**{f"reject_reason::{reason_key}": 1})
            if bool(getattr(owner, "_timed_session_active", False)):
                owner._timed_session_rejects = int(getattr(owner, "_timed_session_rejects", 0)) + 1
    owner.undo_act.setEnabled(owner.controller.can_undo())
    owner.redo_act.setEnabled(owner.controller.can_redo())
    if rejected:
        owner._request_ui_refresh("standard-actions")
        owner.controller.append_audit_event(
            "suggestions_rejected",
            image_id=owner.primary_image.id,
            count=rejected,
            reason=reason_key,
        )
    owner._status_success(f"Rejected {rejected} suggestion(s).", source="assist.reject.visible")
    owner._refresh_assist_warmup_panel()


def accept_suggestions_in_roi(owner) -> None:
    """Accept the currently visible suggestions inside the active ROI."""
    if not owner._ensure_annotation_write_context_confirmed("Accept suggestions in ROI"):
        return
    visible = owner._visible_suggestions()
    candidates = [s for s in visible if owner._point_in_roi(float(s.x), float(s.y))]
    blocked = 0
    allowed: list[PointSuggestion] = []
    for suggestion in candidates:
        accept_guard = getattr(owner, "_ensure_suggestion_accept_allowed", None)
        if accept_guard is not None and not accept_guard(
            suggestion,
            action_label="Accept suggestion in ROI",
            source="assist.accept.roi",
        ):
            blocked += 1
            continue
        allowed.append(suggestion)
    candidates = allowed
    accepted = 0
    for suggestion in list(candidates):
        cmd = AcceptSuggestionCommand(owner.controller, owner.primary_image.id, suggestion.suggestion_id)
        if owner.controller.execute_view_command(cmd):
            accepted += 1
            owner.controller.update_suggestion_metrics(correction_distance=0.0)
            if getattr(owner, "_interactive_learning_enabled", lambda: False)():
                owner._interactive_learning_model.add_example(suggestion, accepted=True)
            if bool(getattr(owner, "_timed_session_active", False)):
                owner._timed_session_accepts = int(getattr(owner, "_timed_session_accepts", 0)) + 1
                owner._timed_session_points = int(getattr(owner, "_timed_session_points", 0)) + 1
    owner.undo_act.setEnabled(owner.controller.can_undo())
    owner.redo_act.setEnabled(owner.controller.can_redo())
    if accepted:
        owner._note_annotation_edit(owner.primary_image.id)
        owner._refresh_table()
        owner._request_ui_refresh("standard-actions")
        owner._schedule_qc_validation(owner.primary_image.id)
        owner.controller.append_audit_event(
            "suggestions_accepted_in_roi",
            image_id=owner.primary_image.id,
            count=accepted,
        )
    status_msg = f"Accepted {accepted} suggestion(s) in ROI."
    if blocked:
        status_msg += f" {blocked} stale suggestion(s) were blocked."
    owner._status_success(status_msg, source="assist.accept.roi")
    owner._refresh_assist_warmup_panel()


def clear_suggestions_current_image(owner) -> None:
    """Clear pending suggestions for the current image."""
    cmd = ClearSuggestionsCommand(owner.controller, owner.primary_image.id)
    if not owner.controller.execute_view_command(cmd):
        owner._status_info("No suggestions to clear.", source="assist.clear")
        return
    owner.undo_act.setEnabled(owner.controller.can_undo())
    owner.redo_act.setEnabled(owner.controller.can_redo())
    owner._request_ui_refresh("standard-actions")
    owner._status_success("Cleared suggestions.", source="assist.clear")
    owner._refresh_assist_warmup_panel()
