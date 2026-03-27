"""Service binding and startup helpers for the main Qt window."""

from __future__ import annotations


def bootstrap_ui(owner) -> None:
    """Build widgets and then attach signal-driven runtime integrations."""
    owner._setup_ui()
    owner._finalize_runtime_startup()


def wire_view_sync_runtime(owner) -> None:
    """Attach linked-view runtime handlers after widgets exist."""
    if owner.view_sync is None:
        return
    owner.view_sync.view_changed.connect(owner._on_view_sync_changed)
    owner.view_sync.enable_zoom_sync(owner.link_zoom)
    owner.view_sync.enable_pan_sync(owner.link_zoom)


def restore_runtime_action_state(owner) -> None:
    """Restore widget-backed runtime toggles after UI setup."""
    if hasattr(owner, "show_smlm_points_act"):
        owner.show_smlm_points = owner.show_smlm_points_act.isChecked()
    if hasattr(owner, "show_smlm_sr_act"):
        owner.show_sr_overlay = owner.show_smlm_sr_act.isChecked()
    if owner.orthoview_widget is not None:
        owner.orthoview_widget.set_callbacks(
            owner._on_orthoview_xz_click,
            owner._on_orthoview_yz_click,
        )


def bind_runtime_services(owner) -> None:
    """Bind queued signals, recorder hooks, and global exception handling."""
    owner._attach_recorder()
    owner._install_exception_hook()
    owner._setup_tool_router()
    owner._bind_events()
    owner._bind_job_signals()


def initialize_session_view(owner) -> None:
    """Load initial images and establish the first synchronized viewport."""
    owner._ensure_loaded(owner.current_image_idx)
    owner._ensure_loaded(owner.support_image_idx)
    owner._reset_crop(initial=True)
    owner._reset_roi()
    owner._request_render_refresh("initial-window-render", debounce=True)


def start_background_runtime(owner) -> None:
    """Start low-priority background services after the first UI frame is queued."""
    owner._schedule_qc_validation()
    owner._autosave_timer.start()


def finalize_runtime_startup(owner) -> None:
    """Complete GUI startup after UI setup and signal binding."""
    if hasattr(owner, "_update_analysis_panel_modalities"):
        owner._update_analysis_panel_modalities()
    wire_view_sync_runtime(owner)
    owner._init_modality_playback()
    owner._cleanup_recent_images()
    restore_runtime_action_state(owner)
    bind_runtime_services(owner)
    initialize_session_view(owner)
    start_background_runtime(owner)
