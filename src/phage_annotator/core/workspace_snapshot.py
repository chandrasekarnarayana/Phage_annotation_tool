"""Central workspace snapshot model with explicit 3-layer state.

This module provides one canonical place to describe and capture runtime state
needed for reproducible save/load of a full workspace.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any, Dict, Mapping, Optional

from phage_annotator.session.signal_hub import emit_display_changed
from phage_annotator.constants.settings import DEFAULTS as SETTINGS_DEFAULTS

WORKSPACE_SNAPSHOT_SCHEMA = "workspace_snapshot.v1"


# ---------------------------------------------------------------------------
# State dataclasses
# ---------------------------------------------------------------------------

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


from phage_annotator.core.workspace_snapshot_ops import (
    workspace_layer_registry,
    apply_workspace_snapshot_to_controller,
    build_workspace_snapshot,
    extract_ui_workspace_state,
)

__all__ = [
    "ProjectLayerState", "SessionWorkspaceLayerState",
    "SettingsPreferencesLayerState", "WorkspaceSnapshot",
    "workspace_layer_registry", "apply_workspace_snapshot_to_controller",
    "build_workspace_snapshot", "extract_ui_workspace_state",
]
