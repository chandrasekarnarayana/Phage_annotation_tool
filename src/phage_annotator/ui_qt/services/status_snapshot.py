"""Services status snapshot helpers for the phage annotation tool.

This module was split from a larger implementation to keep responsibilities
small and file sizes manageable.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from phage_annotator.ui_qt.assist_state import AssistState, assist_state_label
from phage_annotator.ui_qt.services.status_actions import (
    build_action_disabled_reason,
    build_action_enabled,
)
from phage_annotator.ui_qt.services.status_details_payload import build_details_payload
from phage_annotator.ui_qt.services.status import StatusModel, StatusText
from phage_annotator.ui_qt.services.status_derived_core import DerivedStatusSnapshot

def build_status_snapshot(owner: Any):
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
    action_enabled = build_action_enabled(
        owner,
        has_image=has_image,
        has_annotations=has_annotations,
        has_suggestions=has_suggestions,
        has_writable_context=has_writable_context,
        roi_defined=roi_defined,
        selection_count=selection_count,
        can_assist=can_assist,
        can_review=can_review,
        can_export_annotations=can_export_annotations,
        can_measure=can_measure,
        has_qc=has_qc,
    )
    action_disabled_reason = build_action_disabled_reason()

    details_payload = build_details_payload(owner, locals())

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
        details_payload=details_payload)
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
        action_disabled_reason=action_disabled_reason)
