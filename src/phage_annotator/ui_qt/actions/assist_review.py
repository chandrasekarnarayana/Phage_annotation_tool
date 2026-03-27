"""Assist review queue and suggestion-decision helpers."""

from __future__ import annotations

import time

import numpy as np
from matplotlib.backends.qt_compat import QtGui, QtWidgets

from phage_annotator.core.annotation import PointSuggestion
from phage_annotator.session.suggestion_commands import AcceptSuggestionCommand, RejectSuggestionCommand
from phage_annotator.ui_qt.assist_state import assist_state_label


def review_throughput_snapshot(owner) -> tuple[str, float]:
    """Return compact throughput text and avg seconds per decision."""
    metrics = dict(getattr(owner.controller.session_state, "suggestion_metrics", {}) or {})
    accepted = int(metrics.get("accepted", 0))
    rejected = int(metrics.get("rejected", 0))
    start_ts = getattr(owner, "_review_telemetry_started_ts", None)
    if start_ts is None:
        owner._review_telemetry_started_ts = float(time.time())
        owner._review_telemetry_baseline_accepted = accepted
        owner._review_telemetry_baseline_rejected = rejected
        return ("Throughput: n/a", 0.0)
    elapsed_min = max(1e-6, (float(time.time()) - float(start_ts)) / 60.0)
    d_acc = max(0, accepted - int(getattr(owner, "_review_telemetry_baseline_accepted", 0)))
    d_rej = max(0, rejected - int(getattr(owner, "_review_telemetry_baseline_rejected", 0)))
    total = d_acc + d_rej
    acc_pm = d_acc / elapsed_min
    rej_pm = d_rej / elapsed_min
    sec_per = (float(time.time()) - float(start_ts)) / max(1, total)
    return (f"Throughput: A/min {acc_pm:.1f} | R/min {rej_pm:.1f} | s/decision {sec_per:.1f}", sec_per)


def calibration_sparkline_text(owner) -> str:
    """Return a small calibration sparkline from accepted/rejected history."""
    rows = owner.controller.get_suggestion_calibration_samples()
    if not rows:
        return "Calibration: -"
    bins = np.linspace(0.0, 1.0, 6)
    levels = "▁▂▃▄▅▆▇█"
    parts = []
    for i in range(len(bins) - 1):
        lo, hi = bins[i], bins[i + 1]
        slice_rows = [v for p, v in rows if (p >= lo and (p < hi or (i == len(bins) - 2 and p <= hi)))]
        if not slice_rows:
            parts.append("·")
            continue
        rate = float(sum(slice_rows)) / float(len(slice_rows))
        idx = int(round(rate * (len(levels) - 1)))
        parts.append(levels[max(0, min(len(levels) - 1, idx))])
    return f"Calibration: {''.join(parts)}"


def review_queue_progress_counts(owner) -> tuple[int, int]:
    """Return processed/total counts for the current review scope."""
    image_id = owner.primary_image.id
    t_idx = int(owner.t_slider.value())
    z_idx = int(owner.z_slider.value())
    pending = owner._visible_suggestions_uncertain_first()
    history = list(getattr(owner.controller.session_state, "suggestion_history", {}).get(image_id, []))
    processed = 0
    for row in history:
        if int(getattr(row, "t", -2)) not in (t_idx, -1):
            continue
        if int(getattr(row, "z", -2)) not in (z_idx, -1):
            continue
        if str(getattr(row, "status", "")) in ("accepted", "rejected"):
            processed += 1
    return processed, int(processed + len(pending))


def refresh_review_queue_panel(owner) -> None:
    """Refresh the review queue UI without keeping the logic in standard.py."""
    panel = getattr(owner, "review_queue_panel", None)
    if panel is None:
        owner._refresh_suggestion_explain_panel(None)
        return
    t_idx = int(owner.t_slider.value())
    z_idx = int(owner.z_slider.value())
    ranked = owner._visible_suggestions_uncertain_first()
    queue_filter = str(
        getattr(getattr(owner, "review_queue_panel", None), "filter_combo", None).currentData()
        if getattr(owner, "review_queue_panel", None) is not None
        else "all"
    )
    queue_sort = str(
        getattr(getattr(owner, "review_queue_panel", None), "sort_combo", None).currentData()
        if getattr(owner, "review_queue_panel", None) is not None
        else "confidence"
    )
    if queue_filter == "new_only":
        ranked = [s for s in ranked if str(dict(getattr(s, "meta", {}) or {}).get("candidate_class", "")) == "new"]
    elif queue_filter == "conflicts_only":
        ranked = [s for s in ranked if str(dict(getattr(s, "meta", {}) or {}).get("candidate_class", "")) == "conflict"]
    elif queue_filter == "near_existing":
        ranked = [s for s in ranked if str(dict(getattr(s, "meta", {}) or {}).get("candidate_class", "")) == "near_existing"]
    elif queue_filter == "high_confidence":
        ranked = [s for s in ranked if float(dict(getattr(s, "meta", {}) or {}).get("p_accept", getattr(s, "score", 0.0))) >= 0.75]
    elif queue_filter == "high_uncertainty":
        ranked = [s for s in ranked if float(getattr(s, "uncertainty_score", dict(getattr(s, "meta", {}) or {}).get("uncertainty_score", 0.0)) or 0.0) >= 0.5]
    elif queue_filter == "heuristic_only":
        ranked = [s for s in ranked if not bool(dict(getattr(s, "meta", {}) or {}).get("confidence_available", False))]
    elif queue_filter == "dense_ambiguity":
        ranked = [s for s in ranked if "dense_region_ambiguity" in str(getattr(s, "uncertainty_reason", dict(getattr(s, "meta", {}) or {}).get("uncertainty_reason", "")) or "")]
    elif queue_filter == "control_contradiction":
        ranked = [s for s in ranked if float(getattr(s, "control_contradiction_score", dict(getattr(s, "meta", {}) or {}).get("control_contradiction_score", 0.0)) or 0.0) > 0.0]
    elif queue_filter == "current_roi":
        roi_name = str(getattr(owner, "_active_roi_name", "") or "")
        if roi_name:
            ranked = [s for s in ranked if str(getattr(s, "roi_id", "") or "") == roi_name]
    elif queue_filter == "current_frame":
        t_idx = int(owner.t_slider.value())
        z_idx = int(owner.z_slider.value())
        ranked = [s for s in ranked if int(getattr(s, "t", -1)) in (t_idx, -1) and int(getattr(s, "z", -1)) in (z_idx, -1)]
    if queue_sort == "nearest_truth":
        ranked = sorted(ranked, key=lambda s: float(dict(getattr(s, "meta", {}) or {}).get("distance_to_nearest_accepted", 1e9)))
    elif queue_sort == "uncertainty":
        ranked = sorted(
            ranked,
            key=lambda s: float(getattr(s, "uncertainty_score", dict(getattr(s, "meta", {}) or {}).get("uncertainty_score", 0.0)) or 0.0),
            reverse=True,
        )
    elif queue_sort == "evidence_quality":
        ranked = sorted(
            ranked,
            key=lambda s: (
                float(getattr(s, "cross_modality_consistency_score", dict(getattr(s, "meta", {}) or {}).get("cross_modality_consistency_score", 1.0)) or 0.0)
                - float(getattr(s, "control_contradiction_score", dict(getattr(s, "meta", {}) or {}).get("control_contradiction_score", 0.0)) or 0.0)
            ),
            reverse=True,
        )
    elif queue_sort == "batch_id":
        ranked = sorted(ranked, key=lambda s: str(dict(getattr(s, "meta", {}) or {}).get("batch_id", getattr(s, "suggestion_id", ""))))
    else:
        ranked = sorted(
            ranked,
            key=lambda s: float(dict(getattr(s, "meta", {}) or {}).get("p_accept", getattr(s, "score", 0.0))),
            reverse=True,
        )
    if ranked and hasattr(owner, "_set_right_dock_mode"):
        owner._set_right_dock_mode("review")
    panel.context_lbl.setText(f"Effective Assist Context: {owner._effective_assist_context_line(ranked)}")
    delta_txt = str(getattr(owner, "_last_assist_context_delta_text", "")).strip()
    panel.context_delta_lbl.setText(delta_txt)
    panel.context_delta_lbl.setVisible(bool(delta_txt))
    visible_count = len(ranked)
    roi_count = len([s for s in ranked if owner._point_in_roi(float(s.x), float(s.y))]) if hasattr(owner, "_point_in_roi") else visible_count
    panel.remaining_lbl.setText(f"Uncertain remaining: {visible_count} | current ROI: {roi_count}")
    throughput_txt, _sec_per = review_throughput_snapshot(owner)
    panel.telemetry_lbl.setText(throughput_txt)
    panel.calib_spark_lbl.setText(calibration_sparkline_text(owner))
    if getattr(owner, "_settings", None) is not None:
        show_hint = bool(owner._settings.value("firstRunHintReviewQueue", True, type=bool))
        panel.first_run_hint_lbl.setVisible(show_hint)
        if show_hint:
            owner._settings.setValue("firstRunHintReviewQueue", False)
    processed, total = review_queue_progress_counts(owner)
    panel.progress_lbl.setText(f"Progress: {processed} / {total}")
    panel.progress_bar.setValue(int(round(100.0 * float(processed) / max(1.0, float(total)))) if total > 0 else 0)
    freshness = owner._suggestion_freshness_state(owner.primary_image.id, ranked)
    assist_state = owner._canonical_assist_state(ranked)
    need = owner._assist_context_need_count(ranked)
    metrics = dict(getattr(owner.controller.session_state, "suggestion_metrics", {}) or {})
    trained_pos = int(metrics.get("accepted", 0))
    trained_neg = int(metrics.get("rejected", 0))
    readiness_txt = f" (Need {need} more labels in this context)" if assist_state.name == "HEURISTIC" and need > 0 else ""
    panel.header_lbl.setText(
        f"Assist - T={t_idx + 1} Z={z_idx + 1} | Assist: {assist_state_label(assist_state)}{readiness_txt} | trained on: {trained_pos} pos / {trained_neg} neg"
    )
    owner._style_assist_state_label(panel.assist_lbl, assist_state, prefix="Assist state: ", suffix=readiness_txt)
    if not ranked:
        panel.coords_lbl.setText("(x=-, y=-)")
        panel.score_lbl.setText("Acceptance likelihood (p_accept): n/a")
        panel.stale_lbl.setText("staleness: n/a")
        panel.details_lbl.setText("No uncertain suggestions on current frame/scope.")
        for attr in ("accept_btn", "accept_next_btn", "reject_btn", "skip_btn", "next_uncertain_btn", "accept_green_btn"):
            getattr(panel, attr).setEnabled(False)
        if hasattr(panel, "set_suggestions"):
            panel.set_suggestions([], 0)
        owner._refresh_suggestion_explain_panel(None)
        return
    owner._suggestion_cursor = int(max(0, min(int(getattr(owner, "_suggestion_cursor", 0)), len(ranked) - 1)))
    current = ranked[owner._suggestion_cursor]
    if hasattr(panel, "set_suggestions"):
        rows = []
        for idx, suggestion in enumerate(ranked, start=1):
            meta = dict(getattr(suggestion, "meta", {}) or {})
            acceptance = meta.get("p_accept")
            rows.append(
                {
                    "index": idx,
                    "x": int(round(float(suggestion.x))),
                    "y": int(round(float(suggestion.y))),
                    "t": int(getattr(suggestion, "t", -1)),
                    "z": int(getattr(suggestion, "z", -1)),
                    "acceptance": "heuristic" if acceptance is None else f"{float(acceptance):.2f}",
                    "state": str(meta.get("candidate_class", getattr(suggestion, "status", "proposed"))).replace("_", " "),
                    "status": str(getattr(suggestion, "status", "proposed")),
                    "suggestion_id": str(getattr(suggestion, "suggestion_id", "")),
                }
            )
        panel.set_suggestions(rows, owner._suggestion_cursor)
    panel.coords_lbl.setText(f"(x={int(round(float(current.x)))}, y={int(round(float(current.y)))})")
    candidate_class = str(dict(getattr(current, "meta", {}) or {}).get("candidate_class", "new")).strip().replace("_", " ")
    p_accept = dict(getattr(current, "meta", {}) or {}).get("p_accept")
    uncertainty_score = float(getattr(current, "uncertainty_score", dict(getattr(current, "meta", {}) or {}).get("uncertainty_score", 0.0)) or 0.0)
    uncertainty_reason = str(getattr(current, "uncertainty_reason", dict(getattr(current, "meta", {}) or {}).get("uncertainty_reason", "")) or "")
    if p_accept is None:
        panel.score_lbl.setText(f"Acceptance likelihood (p_accept): n/a | generator score: {float(current.score):.2f}")
        panel.details_lbl.setText(
            f"Heuristic-only proposal; review required. Classification: {candidate_class}. "
            f"Uncertainty {uncertainty_score:.2f}{f' ({uncertainty_reason})' if uncertainty_reason else ''}."
        )
    else:
        p_val = float(p_accept)
        triage = "likely accept" if p_val >= 0.75 else "needs review" if p_val >= 0.5 else "unlikely accept"
        panel.score_lbl.setText(f"Acceptance likelihood (p_accept): {p_val:.2f} ({triage})")
        panel.details_lbl.setText(
            f"Generator score: {float(current.score):.2f} | Classification: {candidate_class} | "
            f"Uncertainty: {uncertainty_score:.2f}{f' ({uncertainty_reason})' if uncertainty_reason else ''}"
        )
    if freshness.get("is_stale", False):
        panel.stale_lbl.setText(f"staleness: Stale - regenerate recommended (generated {freshness.get('age_text', 'n/a')} ago)")
        panel.stale_lbl.setStyleSheet("color: #d84315; font-weight: 600;")
    else:
        panel.stale_lbl.setStyleSheet("")
    for attr in ("accept_btn", "accept_next_btn", "reject_btn", "skip_btn", "next_uncertain_btn"):
        getattr(panel, attr).setEnabled(True)
    panel.accept_green_btn.setEnabled(True)
    owner._refresh_suggestion_explain_panel(current)


def on_review_queue_row_selected(owner, row: int) -> None:
    """Handle row selection from the review queue table."""
    all_rows = owner._suggestions_for_current_tz()
    if not all_rows:
        return
    idx = int(max(0, min(int(row), len(all_rows) - 1)))
    selected = all_rows[idx]
    proposed_ranked = owner._visible_suggestions_uncertain_first()
    if proposed_ranked:
        sid = str(getattr(selected, "suggestion_id", ""))
        for ridx, item in enumerate(proposed_ranked):
            if str(getattr(item, "suggestion_id", "")) == sid:
                owner._suggestion_cursor = ridx
                break
    owner._focus_suggestion(selected)
    owner._refresh_review_queue_panel()


def confirm_suggestion_redecision(owner, target_status: str) -> bool:
    """Confirm destructive accepted->non-accepted transitions."""
    msg = QtWidgets.QMessageBox(owner)
    msg.setIcon(QtWidgets.QMessageBox.Icon.Warning)
    msg.setWindowTitle("Confirm Decision Change")
    msg.setText("This suggestion is already accepted.")
    msg.setInformativeText(
        "Changing it will remove the linked committed annotation.\n"
        f"Continue and set status to {str(target_status)}?"
    )
    msg.setStandardButtons(QtWidgets.QMessageBox.StandardButton.Yes | QtWidgets.QMessageBox.StandardButton.Cancel)
    msg.setDefaultButton(QtWidgets.QMessageBox.StandardButton.Cancel)
    return msg.exec() == QtWidgets.QMessageBox.StandardButton.Yes


def set_selected_suggestion_decision(owner, suggestion_id: str, status: str) -> None:
    """Change suggestion decision through the controller/command layer."""
    image_id = int(owner.primary_image.id)
    sid = str(suggestion_id or "").strip()
    target_status = str(status or "").strip().lower()
    if not sid or target_status not in {"accepted", "rejected", "proposed"}:
        return
    if target_status == "accepted" and not owner._ensure_annotation_write_context_confirmed(
        "Change suggestion decision to accepted"
    ):
        return
    decision_ctx = owner.controller.get_suggestion_decision_context(image_id, sid)
    pending_item = decision_ctx.get("pending_item")
    suggestion = decision_ctx.get("suggestion")
    if suggestion is None:
        owner._status_warning("Suggestion not found for decision update.", source="assist.review")
        return
    current_status = str(decision_ctx.get("status", "") or "proposed")
    if current_status == target_status:
        owner._status_info(f"Suggestion already {target_status}.", source="assist.review")
        return
    if current_status == "accepted" and target_status in {"rejected", "proposed"} and not confirm_suggestion_redecision(owner, target_status):
        owner._status_info("Decision change cancelled.", source="assist.review")
        return
    if target_status == "accepted":
        accept_guard = getattr(owner, "_ensure_suggestion_accept_allowed", None)
        if accept_guard is not None and not accept_guard(
            suggestion,
            action_label="Accept selected suggestion",
            source="assist.review",
        ):
            return
    if pending_item is not None and target_status == "accepted":
        cmd = AcceptSuggestionCommand(owner.controller, image_id, sid)
        if not owner.controller.execute_view_command(cmd):
            owner._status_error("Could not set accepted for selected suggestion.", source="assist.review")
            return
    elif pending_item is not None and target_status == "rejected":
        cmd = RejectSuggestionCommand(owner.controller, image_id, sid)
        if not owner.controller.execute_view_command(cmd):
            owner._status_error("Could not set rejected for selected suggestion.", source="assist.review")
            return
    else:
        if not owner.controller.update_suggestion_decision(int(image_id), sid, target_status):
            owner._status_error("Could not update suggestion decision.", source="assist.review")
            return
        if hasattr(owner.controller, "append_audit_event"):
            owner.controller.append_audit_event(
                "suggestion_decision_changed",
                image_id=int(image_id),
                suggestion_id=sid,
                status=target_status,
            )
    owner.undo_act.setEnabled(owner.controller.can_undo())
    owner.redo_act.setEnabled(owner.controller.can_redo())
    owner._note_annotation_edit(image_id)
    owner._refresh_table()
    owner._request_ui_refresh("standard-actions", table=True)
    owner._schedule_qc_validation(image_id)
    owner._refresh_assist_warmup_panel()
    owner._status_success(f"Suggestion decision set to {target_status}.", source="assist.review")
