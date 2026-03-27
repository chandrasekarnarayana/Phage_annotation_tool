"""Derived status builder for the compact status bar and details panel.

This module keeps status derivation separate from widget rendering so the
presenter can stay focused on message priority, timing, and anti-flicker
behavior. The builder reads already-available GUI/session state and assembles
one structured snapshot that feeds both the bottom status bar and the expanded
details panel.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

from phage_annotator.ui_qt.assist_state import AssistState, assist_state_label
from phage_annotator.ui_qt.services.status import StatusModel, StatusText


@dataclass(slots=True)
class DerivedStatusSnapshot:
    """Structured snapshot shared by compact and detailed status views."""

    model: StatusModel
    dataset_name: str
    frame_txt: str
    current_count: int
    total_count: int
    scope_state: str
    target_state: str
    modality_txt: str
    assist_state: AssistState
    assist_need: int
    freshness: dict[str, Any]
    tool_name: str
    cache_mb: float
    cache_items: int
    action_enabled: dict[str, bool]
    action_disabled_reason: dict[str, str]


def build_status_snapshot(owner: Any) -> DerivedStatusSnapshot:
    """Build a unified status snapshot from current window/controller state."""
    total = sum(len(v) for v in owner.annotations.values())
    current = len(
        [kp for kp in owner._current_keypoints() if kp.t == owner.t_slider.value() or kp.t == -1]
    )
    dataset_name = str(getattr(owner.primary_image, "name", "unknown"))
    array = getattr(owner.primary_image, "array", None)
    t_total = (
        int(array.shape[0])
        if array is not None and getattr(array, "ndim", 0) >= 1
        else int(owner.t_slider.maximum() + 1)
    )
    z_total = (
        int(array.shape[1])
        if array is not None and getattr(array, "ndim", 0) >= 2
        else int(owner.z_slider.maximum() + 1)
    )
    frame_txt = (
        f"T: {int(owner.t_slider.value()) + 1}/{max(1, t_total)} | "
        f"Z: {int(owner.z_slider.value()) + 1}/{max(1, z_total)}"
    )

    modality_txt = f"Modality {int(getattr(owner, '_active_modality_idx', -1))}"
    controller = getattr(owner, "controller", None)
    manager = (
        getattr(controller.session_state, "modality_manager", None)
        if controller is not None
        else None
    )
    if manager is not None:
        try:
            for modality in manager.get_all_modalities():
                if int(modality.image_id) == int(owner.primary_image.id):
                    modality_txt = str(modality.display_name)
                    break
        except Exception:
            pass

    pts_view, view_area_um2 = owner._view_density_stats()
    view_density = (pts_view / view_area_um2) if view_area_um2 > 0 else 0.0
    pts_roi_total, roi_total_area_um2 = owner._roi_total_stats()
    roi_total_density = (pts_roi_total / roi_total_area_um2) if roi_total_area_um2 > 0 else 0.0
    roi_active = owner.roi_shape != "none" and owner.roi_rect[2] > 0 and owner.roi_rect[3] > 0

    cache_mb, cache_items = owner.proj_cache.stats()
    diag_flags: list[str] = []
    render_scales = getattr(owner, "_render_scales", {}) or {}
    scale = max(render_scales.values()) if render_scales else 1
    if scale > 1:
        diag_flags.append(f"Downsample x{scale}")
    if getattr(owner.primary_image, "downsampled", False):
        diag_flags.append("Spatial 2x downsampled (memory)")
    lod_active = getattr(owner, "_lod_mode_active", {})
    if lod_active.get(owner.primary_image.id, False):
        diag_flags.append("LOD")
    if getattr(owner.primary_image.array, "filename", None) is not None:
        diag_flags.append("Memmap")

    assist_state = owner._canonical_assist_state()
    need = owner._assist_context_need_count()

    jobs_txt = "idle"
    if getattr(owner, "jobs", None) is not None:
        try:
            job_count = int(owner.jobs.active_job_count())
            if job_count > 0:
                jobs_txt = f"{job_count} ({getattr(owner, '_active_job_name', 'running')})"
        except Exception:
            pass

    autosave_enabled = bool(
        getattr(owner, "_settings", None).value("autosaveRecoveryEnabled", True, type=bool)
        if getattr(owner, "_settings", None) is not None
        else True
    )
    autosave_txt = "off"
    if autosave_enabled:
        autosave_txt = "recent" if getattr(owner, "_last_autosave_timestamp", None) else "on"

    scope_state = "Stack" if str(getattr(owner, "annotation_scope", "current")) == "all" else "Slice"
    panel_map = dict(getattr(owner, "_panel_modality_map", {}) or {})
    default_target = owner._default_panel_key() if hasattr(owner, "_default_panel_key") else "modality_0"
    target_key = str(getattr(owner, "annotate_target", default_target))
    target_state = str(getattr(panel_map.get(target_key), "display_name", target_key.title()))
    context_spec = {}
    binding = {}
    controller = getattr(owner, "controller", None)
    if controller is not None:
        try:
            if hasattr(controller, "current_annotation_context"):
                context_spec = dict(controller.current_annotation_context() or {})
        except Exception:
            context_spec = {}
        try:
            if hasattr(controller, "annotation_binding_for_panel"):
                binding = dict(controller.annotation_binding_for_panel(target_key) or {})
        except Exception:
            binding = {}
    write_mode = str(context_spec.get("mode", context_spec.get("ownership_mode", "independent")) or "independent")
    ownership_mode = str(context_spec.get("ownership_mode", write_mode) or write_mode)
    if write_mode == "read_only":
        write_mode_label = "Read-only overlay"
    elif ownership_mode == "shared_source":
        write_mode_label = "Shared with source"
    else:
        write_mode_label = "Independent"
    context_key_label = str(context_spec.get("context_key", "") or target_key or "-")
    binding_path = str(binding.get("path", "") or "")
    binding_label = Path(binding_path).name if binding_path else "Unbound"
    sync_group = "-"
    sync_modes_label = "Contrast, Zoom/Pan, Playback"
    try:
        if hasattr(owner, "_sync_key_for_panel"):
            sync_group = str(owner._sync_key_for_panel(target_key) or "").strip() or "-"
        sync_modes: list[str] = []
        if hasattr(owner, "_sync_mode_enabled_for_panel"):
            if bool(owner._sync_mode_enabled_for_panel(target_key, "contrast")):
                sync_modes.append("Contrast")
            if bool(owner._sync_mode_enabled_for_panel(target_key, "zoom")):
                sync_modes.append("Zoom/Pan")
            if bool(owner._sync_mode_enabled_for_panel(target_key, "playback")):
                sync_modes.append("Playback")
        sync_modes_label = ", ".join(sync_modes) if sync_modes else "None"
    except Exception:
        sync_group = "-"
        sync_modes_label = "Unknown"
    qc_warnings = 0
    qc_errors = 0
    qc_state = getattr(owner, "qc_state", None)
    if qc_state is not None:
        for issue in getattr(qc_state, "issues", []):
            sev = str(getattr(getattr(issue, "severity", None), "value", "")).lower()
            if sev == "warning":
                qc_warnings += 1
            elif sev == "error":
                qc_errors += 1
    qc_total = qc_warnings + qc_errors
    qc_label = "QC: no issues" if qc_total == 0 else f"QC: {qc_warnings} warnings"
    if qc_errors > 0:
        qc_label += f", {qc_errors} errors"

    freshness = (
        owner._suggestion_freshness_state(owner.primary_image.id)
        if hasattr(owner, "_suggestion_freshness_state")
        else {"has_suggestions": False, "age_text": "n/a", "is_stale": False}
    )
    if not freshness.get("has_suggestions", False):
        suggestions_text = "Suggestions: n/a"
    elif freshness.get("is_stale", False):
        suggestions_text = f"Suggestions: {freshness.get('age_text', 'n/a')} old (Stale)"
    else:
        suggestions_text = f"Suggestions: {freshness.get('age_text', 'n/a')} old"

    tool_name = "Annotate"
    try:
        if getattr(owner, "tool_router", None) is not None:
            tool_name = owner._tool_label(owner.tool_router.tool)
    except Exception:
        pass

    if getattr(owner, "_playback_mode", False):
        idle_text = "Playback running"
        buffer_stats = None
        ring = getattr(owner, "_playback_ring", None)
        if ring is not None:
            try:
                stats = ring.stats()
                buffer_stats = (
                    f"Buffer {stats.filled}/{stats.capacity} | "
                    f"Underruns {int(getattr(owner, '_playback_underruns', 0))}"
                )
            except Exception:
                buffer_stats = None
        metric_text = buffer_stats or f"FPS {int(owner.speed_slider.value())}"
    elif bool(getattr(owner, "_assist_mode_enabled", False)):
        idle_text = StatusText.REVIEWING_SUGGESTIONS
        metric_text = qc_label if qc_total > 0 else suggestions_text
    elif roi_active and roi_total_area_um2 > 0:
        idle_text = StatusText.READY_FOR_ANNOTATION
        metric_text = f"ROI {roi_total_area_um2:.2f} um² | Density {roi_total_density:.3f}/um²"
    elif view_area_um2 > 0:
        idle_text = StatusText.READY_FOR_ANNOTATION
        metric_text = f"Visible {pts_view} | Density {view_density:.3f}/um²"
    else:
        idle_text = StatusText.READY_FOR_ANNOTATION
        metric_text = f"Slice {current} | Total {total}"

    alert_text = ""
    alert_severity = None
    pending_context = bool(
        hasattr(owner, "_is_annotation_context_guard_pending")
        and owner._is_annotation_context_guard_pending()
    )
    if pending_context:
        alert_text = "Write context pending confirmation"
        alert_severity = "warning"
    elif bool(freshness.get("is_stale", False)):
        alert_text = StatusText.SUGGESTIONS_STALE
        alert_severity = "warning"
    elif qc_total > 0 and not bool(getattr(owner, "_playback_mode", False)):
        alert_text = qc_label
        alert_severity = "warning"

    context_parts = [
        dataset_name,
        f"T{int(owner.t_slider.value()) + 1} Z{int(owner.z_slider.value()) + 1}",
        f"Tool: {tool_name}",
        f"Label: {owner.current_label}",
    ]

    has_image = bool(getattr(owner, "primary_image", None) is not None)
    has_annotations = total > 0
    has_slice_annotations = current > 0
    suggestions_map = getattr(owner, "suggestions", {}) or {}
    image_suggestions = list(suggestions_map.get(getattr(owner.primary_image, "id", -1), []) or [])
    has_suggestions = bool(freshness.get("has_suggestions", False) or image_suggestions)
    has_qc = qc_total > 0
    selection_count = 0
    annot_table = getattr(owner, "annot_table", None)
    if annot_table is not None:
        try:
            selection_count = int(len(annot_table.selectionModel().selectedRows()))
        except Exception:
            selection_count = 0
    roi_defined = bool(roi_active)
    results_rows = owner._bottom_task_counts()[1]
    can_review = has_annotations
    has_writable_context = write_mode != "read_only"
    can_assist = bool(has_image and has_writable_context)
    can_export_annotations = bool(has_image and has_writable_context)
    can_measure = bool(has_image and (has_annotations or roi_defined))
    action_enabled = {
        "load_ann_current_act": has_image,
        "load_ann_multi_act": True,
        "load_ann_all_act": has_image,
        "reload_ann_act": has_image,
        "save_proj_act": has_image,
        "load_proj_act": True,
        "save_csv_act": can_export_annotations,
        "save_json_act": can_export_annotations,
        "export_view_act": has_image,
        "copy_display_act": has_image,
        "measure_act": can_measure,
        "clear_roi_act": roi_defined,
        "copy_roi_to_all_act": roi_defined,
        "save_roi_template_act": roi_defined,
        "apply_roi_template_act": has_image,
        "suggest_points_act": can_assist,
        "suggest_points_image_act": can_assist,
        "select_suggestion_strategy_act": has_image,
        "load_suggestion_rule_config_act": has_image,
        "set_suggestion_score_threshold_act": has_image,
        "accept_visible_suggestions_act": has_suggestions and has_writable_context,
        "accept_green_suggestions_act": has_suggestions and has_writable_context,
        "accept_suggestions_in_roi_act": has_suggestions and has_writable_context and roi_defined,
        "reject_visible_suggestions_act": has_suggestions and has_writable_context,
        "clear_suggestions_act": has_suggestions,
        "show_suggestion_patch_act": has_suggestions,
        "show_all_predictions_act": has_suggestions,
        "toggle_suggestions_overlay_act": has_image,
        "start_timed_session_assisted_act": has_image,
        "start_timed_session_manual_act": has_image,
        "stop_timed_session_act": bool(getattr(owner, "_timed_session_active", False)),
        "assist_warmup_act": can_assist,
        "train_ranker_now_act": has_annotations,
        "show_calibration_visualizer_act": has_annotations,
        "batch_correct_suggestions_act": has_suggestions and has_writable_context,
        "propagate_suggestions_act": has_suggestions and has_writable_context,
        "set_current_user_act": can_review,
        "mark_selected_in_review_act": selection_count > 0,
        "mark_selected_approved_act": selection_count > 0,
        "mark_selected_needs_changes_act": selection_count > 0,
        "assign_selected_act": selection_count > 0,
        "show_reviewer_analytics_act": has_annotations,
        "queue_all_act": can_review,
        "queue_my_act": can_review,
        "queue_needs_review_act": can_review,
        "queue_blocked_qc_act": has_qc,
        "qc_validate_act": has_annotations,
        "qc_jump_next_act": has_qc,
        "review_context_pack_act": can_review,
        "jump_to_frame_act": has_image,
        "jump_to_z_act": has_image,
        "focus_canvas_mode_act": has_image,
        "advanced_panels_act": True,
        "open_panel_policy_act": True,
        "toggle_profile_act": has_image,
        "toggle_hist_act": has_image,
        "toggle_left_act": True,
        "toggle_settings_act": True,
        "toggle_overlay_act": has_image,
        "save_layout_act": True,
        "undo_layout_change_act": bool(getattr(owner, "_layout_history", None)),
        "save_layout_default_act": True,
        "reset_layout_act": True,
        "link_zoom_act": has_image,
        "show_roi_handles_act": has_image,
        "show_recorder_act": has_image,
        "threshold_act": has_image,
        "analyze_particles_act": has_image,
        "smlm_act": roi_defined,
        "deepstorm_act": roi_defined,
        "rerun_smlm_act": bool(getattr(owner, "_last_smlm_run_config", None)),
        "reset_view_act": has_image,
        "toggle_logs_act": True,
    }
    action_disabled_reason = {
        "load_ann_current_act": "Load an image or select a target context first.",
        "load_ann_all_act": "Load an image set before loading all linked annotations.",
        "reload_ann_act": "Load an image before reloading annotations.",
        "save_proj_act": "Open data before saving a project workspace.",
        "save_csv_act": "Saving annotations requires a writable annotation context.",
        "save_json_act": "Saving annotations requires a writable annotation context.",
        "export_view_act": "Load an image before exporting the current view.",
        "copy_display_act": "Load an image before copying display settings.",
        "measure_act": "Add annotations or define an ROI before measuring.",
        "clear_roi_act": "Define an ROI before clearing it.",
        "copy_roi_to_all_act": "Define an ROI before propagating it.",
        "save_roi_template_act": "Define an ROI before saving it as a template.",
        "apply_roi_template_act": "Load an image before applying an ROI template.",
        "suggest_points_act": "Suggestion generation requires a writable annotation target.",
        "suggest_points_image_act": "Suggestion generation requires a writable annotation target.",
        "select_suggestion_strategy_act": "Load an image before changing the suggestion strategy.",
        "load_suggestion_rule_config_act": "Load an image before loading a suggestion rule configuration.",
        "set_suggestion_score_threshold_act": "Load an image before changing the suggestion threshold.",
        "accept_visible_suggestions_act": "Visible suggestions and a writable target are required.",
        "accept_green_suggestions_act": "Visible suggestions and a writable target are required.",
        "accept_suggestions_in_roi_act": "Visible suggestions, a writable target, and an ROI are required.",
        "reject_visible_suggestions_act": "Visible suggestions and a writable target are required.",
        "clear_suggestions_act": "There are no suggestions to clear.",
        "show_suggestion_patch_act": "There are no suggestions to inspect.",
        "show_all_predictions_act": "There are no suggestions to inspect.",
        "toggle_suggestions_overlay_act": "Load an image before toggling suggestion overlays.",
        "stop_timed_session_act": "No timed session is currently running.",
        "assist_warmup_act": "Warmup requires a writable annotation target.",
        "train_ranker_now_act": "Training requires existing annotations.",
        "show_calibration_visualizer_act": "Calibration requires existing annotations.",
        "batch_correct_suggestions_act": "Visible suggestions and a writable target are required.",
        "propagate_suggestions_act": "Visible suggestions and a writable target are required.",
        "set_current_user_act": "Review actions require existing annotations.",
        "mark_selected_in_review_act": "Select one or more annotations first.",
        "mark_selected_approved_act": "Select one or more annotations first.",
        "mark_selected_needs_changes_act": "Select one or more annotations first.",
        "assign_selected_act": "Select one or more annotations first.",
        "show_reviewer_analytics_act": "Reviewer analytics require existing annotations.",
        "queue_all_act": "Review queue filters require existing annotations.",
        "queue_my_act": "Review queue filters require existing annotations.",
        "queue_needs_review_act": "Review queue filters require existing annotations.",
        "queue_blocked_qc_act": "No QC-blocked annotations are currently available.",
        "qc_validate_act": "QC validation requires existing annotations.",
        "qc_jump_next_act": "There are no QC issues to review.",
        "review_context_pack_act": "Review context requires existing annotations.",
        "jump_to_frame_act": "Load an image before navigating frames.",
        "jump_to_z_act": "Load an image before navigating Z slices.",
        "focus_canvas_mode_act": "Load an image before enabling canvas focus mode.",
        "toggle_profile_act": "Load an image before showing line profiles.",
        "toggle_hist_act": "Load an image before showing histograms.",
        "toggle_overlay_act": "Load an image before toggling overlays.",
        "link_zoom_act": "Load an image before linking synced views.",
        "show_roi_handles_act": "Load an image before showing ROI handles.",
        "show_recorder_act": "Load an image before opening the recorder.",
        "threshold_act": "Load an image before opening threshold controls.",
        "analyze_particles_act": "Load an image before analyzing particles.",
        "smlm_act": "Define an ROI before running ThunderSTORM.",
        "deepstorm_act": "Define an ROI before running Deep-STORM.",
        "rerun_smlm_act": "Run an SMLM workflow once before rerunning it.",
        "reset_view_act": "Load an image before resetting the canvas view.",
    }

    details_payload = {
        "dataset_lbl": dataset_name,
        "tz_lbl": frame_txt,
        "scope_lbl": scope_state,
        "target_lbl": target_state,
        "sync_group_lbl": sync_group,
        "sync_modes_lbl": sync_modes_label,
        "write_mode_lbl": write_mode_label,
        "write_context_lbl": context_key_label,
        "binding_lbl": binding_label,
        "modality_lbl": modality_txt,
        "label_lbl": str(owner.current_label),
        "assist_lbl": f"{assist_state_label(assist_state)}"
        + (f" (Need {need} more labels)" if assist_state == AssistState.HEURISTIC and need > 0 else ""),
        "context_lbl": owner._effective_assist_context_line()
        if hasattr(owner, "_effective_assist_context_line")
        else "-",
        "suggestions_lbl": suggestions_text,
        "qc_lbl": qc_label,
        "results_lbl": "Results: empty" if results_rows <= 0 else f"Results: {results_rows} rows",
        "points_lbl": f"Slice {current} | Total {total}",
        "roi_area_lbl": f"{roi_total_area_um2:.2f} um^2" if roi_total_area_um2 > 0 else "n/a",
        "density_lbl": f"{roi_total_density:.3f} /um^2" if roi_total_area_um2 > 0 else "n/a",
        "fps_lbl": f"{int(owner.speed_slider.value())} fps",
        "autosave_lbl": autosave_txt,
        "cache_lbl": f"{cache_mb} MB | {cache_items} items",
        "jobs_lbl": jobs_txt,
        "diag_lbl": "; ".join(diag_flags) if diag_flags else "none",
    }

    model = StatusModel(
        context_text=" | ".join(part for part in context_parts if part),
        idle_text=idle_text,
        metric_text=metric_text,
        alert_text=alert_text,
        alert_severity=alert_severity,
        sticky_advisory_text=StatusText.UNSAVED_CHANGES,
        dirty=bool(
            getattr(getattr(owner, "controller", None), "session_state", None) is not None
            and bool(getattr(owner.controller.session_state, "dirty", False))
        ),
        details_payload=details_payload,
    )
    return DerivedStatusSnapshot(
        model=model,
        dataset_name=dataset_name,
        frame_txt=frame_txt,
        current_count=current,
        total_count=total,
        scope_state=scope_state,
        target_state=target_state,
        modality_txt=modality_txt,
        assist_state=assist_state,
        assist_need=need,
        freshness=freshness,
        tool_name=tool_name,
        cache_mb=cache_mb,
        cache_items=cache_items,
        action_enabled=action_enabled,
        action_disabled_reason=action_disabled_reason,
    )
