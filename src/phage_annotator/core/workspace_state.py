"""Core workspace state helpers for the phage annotation tool.

This module was split from a larger implementation to keep responsibilities
small and file sizes manageable.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any, Dict, Mapping, Optional

from phage_annotator.session.signal_hub import emit_display_changed

from phage_annotator.constants.settings import DEFAULTS as SETTINGS_DEFAULTS


WORKSPACE_SNAPSHOT_SCHEMA = "workspace_snapshot.v1"


@dataclass
class ProjectLayerState:
    """Project-file layer: persistent project identity and file context."""

    project_path: Optional[str] = None
    project_save_time: Optional[float] = None
    dirty: bool = False
    last_folder: Optional[str] = None
    recent_images: list[str] = field(default_factory=list)
    image_count: int = 0
    annotation_counts: Dict[str, int] = field(default_factory=dict)

@dataclass
class SessionWorkspaceLayerState:
    """Session/workspace layer: active GUI/session state for exact restore."""

    active_primary_id: int = 0
    active_support_id: int = 0
    fps: int = 12
    current_label: str = ""
    labels: list[str] = field(default_factory=list)
    t: int = 0
    z: int = 0
    crop_rect: Optional[tuple[float, float, float, float]] = None
    roi_rect: Optional[tuple[float, float, float, float]] = None
    roi_shape: Optional[str] = None
    tool: str = "ANNOTATE_POINT"
    annotate_target: str = "mean"
    annotation_scope: str = "all"
    linked_zoom: bool = True
    overlay_enabled: bool = True
    show_ann_frame: bool = True
    show_ann_mean: bool = True
    profile_enabled: bool = True
    hist_enabled: bool = True
    hist_bins: int = 100
    hist_region: str = "roi"
    play_mode: Optional[str] = None
    loop_playback: bool = False
    annotation_space: str = "stack"
    generation_space: str = "stack"
    display_mapping_frame: Dict[str, Any] = field(default_factory=dict)
    lazy_sync_groups: Dict[str, str] = field(default_factory=dict)
    lazy_sync_modes: Dict[str, Dict[str, bool]] = field(default_factory=dict)
    roi_by_sync_group: Dict[str, Optional[Dict[str, Any]]] = field(default_factory=dict)
    feature_flags: Dict[str, bool] = field(default_factory=dict)
    workflow_metrics: Dict[str, Any] = field(default_factory=dict)
    ui_workspace: Dict[str, Any] = field(default_factory=dict)

@dataclass
class SettingsPreferencesLayerState:
    """Preferences layer: app-wide settings and defaults."""

    values: Dict[str, Any] = field(default_factory=dict)
    defaults: Dict[str, Any] = field(default_factory=lambda: dict(SETTINGS_DEFAULTS))

@dataclass
class WorkspaceSnapshot:
    """Top-level snapshot with explicit 3-layer model."""

    schema: str = WORKSPACE_SNAPSHOT_SCHEMA
    project: ProjectLayerState = field(default_factory=ProjectLayerState)
    session_workspace: SessionWorkspaceLayerState = field(default_factory=SessionWorkspaceLayerState)
    settings_preferences: SettingsPreferencesLayerState = field(default_factory=SettingsPreferencesLayerState)

    def to_dict(self) -> Dict[str, Any]:
        """Convert dict for the current workflow."""
        return asdict(self)

def workspace_layer_registry() -> Dict[str, list[str]]:
    """List canonical tracked keys by layer."""
    return {
        "project": list(ProjectLayerState.__dataclass_fields__.keys()),
        "session_workspace": list(SessionWorkspaceLayerState.__dataclass_fields__.keys()),
        "settings_preferences": list(SettingsPreferencesLayerState.__dataclass_fields__.keys()),
    }

def _path_to_str(value: Any) -> Optional[str]:
    """Handle the path to str helper flow."""
    if value is None:
        return None
    try:
        return str(Path(value))
    except Exception:
        return str(value)

def build_workspace_snapshot(
    controller: Any,
    settings_preferences: Mapping[str, Any],
    ui_workspace_state: Optional[Mapping[str, Any]] = None,
) -> Dict[str, Any]:
    """Build a full 3-layer snapshot from controller + settings payload."""
    session_state = getattr(controller, "session_state", None)
    view_state = getattr(controller, "view_state", None)

    annotations = getattr(session_state, "annotations", {}) or {}
    annotation_counts = {str(k): len(v) for k, v in annotations.items() if isinstance(v, list)}

    display_mapping_frame: Dict[str, Any] = {}
    try:
        active_id = int(getattr(session_state, "active_primary_id", 0))
        mapping = controller.display_mapping.mapping_for(active_id, "frame")
        display_mapping_frame = {
            "min": float(getattr(mapping, "min_val", 0.0)),
            "max": float(getattr(mapping, "max_val", 1.0)),
            "gamma": float(getattr(mapping, "gamma", 1.0)),
            "lut": int(getattr(mapping, "lut", 0)),
            "invert": bool(getattr(mapping, "invert", False)),
        }
    except Exception:
        display_mapping_frame = {}

    raw_sync_groups = dict(getattr(session_state, "lazy_sync_groups", {}) or {})
    lazy_sync_groups = {
        str(key): str(value).strip()
        for key, value in raw_sync_groups.items()
        if str(value).strip()
    }
    raw_sync_modes = dict(getattr(session_state, "lazy_sync_modes", {}) or {})
    lazy_sync_modes = {
        str(key): {
            "contrast": bool(dict(value or {}).get("contrast", True)),
            "zoom": bool(dict(value or {}).get("zoom", True)),
            "playback": bool(dict(value or {}).get("playback", True)),
        }
        for key, value in raw_sync_modes.items()
    }
    raw_roi_by_group = dict(getattr(session_state, "roi_by_sync_group", {}) or {})
    roi_by_sync_group = {
        str(key): (None if value is None else dict(value))
        for key, value in raw_roi_by_group.items()
        if str(key).strip()
    }

    snapshot = WorkspaceSnapshot(
        project=ProjectLayerState(
            project_path=_path_to_str(getattr(session_state, "project_path", None)),
            project_save_time=getattr(session_state, "project_save_time", None),
            dirty=bool(getattr(session_state, "dirty", False)),
            last_folder=_path_to_str(getattr(session_state, "last_folder", None)),
            recent_images=[str(x) for x in list(getattr(session_state, "recent_images", []))],
            image_count=len(list(getattr(session_state, "images", []))),
            annotation_counts=annotation_counts,
        ),
        session_workspace=SessionWorkspaceLayerState(
            active_primary_id=int(getattr(session_state, "active_primary_id", 0)),
            active_support_id=int(getattr(session_state, "active_support_id", 0)),
            fps=int(getattr(session_state, "fps", 12)),
            current_label=str(getattr(session_state, "current_label", "")),
            labels=[str(x) for x in list(getattr(session_state, "labels", []))],
            t=int(getattr(view_state, "t", 0)),
            z=int(getattr(view_state, "z", 0)),
            crop_rect=getattr(view_state, "crop_rect", None),
            roi_rect=getattr(view_state, "roi_rect", None),
            roi_shape=getattr(view_state, "roi_shape", None),
            tool=str(getattr(view_state, "tool", "ANNOTATE_POINT")),
            annotate_target=str(getattr(view_state, "annotate_target", "mean")),
            annotation_scope=str(getattr(view_state, "annotation_scope", "all")),
            linked_zoom=bool(getattr(view_state, "linked_zoom", True)),
            overlay_enabled=bool(getattr(view_state, "overlay_enabled", True)),
            show_ann_frame=bool(getattr(view_state, "show_ann_frame", True)),
            show_ann_mean=bool(getattr(view_state, "show_ann_mean", True)),
            profile_enabled=bool(getattr(view_state, "profile_enabled", True)),
            hist_enabled=bool(getattr(view_state, "hist_enabled", True)),
            hist_bins=int(getattr(view_state, "hist_bins", 100)),
            hist_region=str(getattr(view_state, "hist_region", "roi")),
            play_mode=getattr(view_state, "play_mode", None),
            loop_playback=bool(getattr(view_state, "loop_playback", False)),
            annotation_space=str(getattr(session_state, "annotation_space", "stack")),
            generation_space=str(getattr(session_state, "generation_space", "stack")),
            display_mapping_frame=display_mapping_frame,
            lazy_sync_groups=lazy_sync_groups,
            lazy_sync_modes=lazy_sync_modes,
            roi_by_sync_group=roi_by_sync_group,
            feature_flags=dict(getattr(session_state, "feature_flags", {}) or {}),
            workflow_metrics=dict(getattr(session_state, "workflow_metrics", {}) or {}),
            ui_workspace=dict(ui_workspace_state or {}),
        ),
        settings_preferences=SettingsPreferencesLayerState(
            values=dict(settings_preferences),
        ),
    )
    return snapshot.to_dict()

def extract_ui_workspace_state(snapshot: Mapping[str, Any]) -> Dict[str, Any]:
    """Return UI workspace payload from snapshot, if present."""
    session_layer = snapshot.get("session_workspace", {})
    if not isinstance(session_layer, dict):
        return {}
    payload = session_layer.get("ui_workspace", {})
    if not isinstance(payload, dict):
        return {}
    return dict(payload)
