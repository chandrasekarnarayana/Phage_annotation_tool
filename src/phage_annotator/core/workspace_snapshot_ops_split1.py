"""Split definitions from workspace_snapshot_ops.py."""

from __future__ import annotations

from pathlib import Path
from typing import Any, Dict, Mapping, Optional

from phage_annotator.session.signal_hub import emit_display_changed
from phage_annotator.constants.settings import DEFAULTS as SETTINGS_DEFAULTS
from phage_annotator.core.workspace_snapshot import (
    ProjectLayerState, SessionWorkspaceLayerState,
    SettingsPreferencesLayerState, WorkspaceSnapshot,
)


# ---------------------------------------------------------------------------
# Registry and helpers
# ---------------------------------------------------------------------------

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

def _get_controller_action_logger(controller: Any) -> Any:
    """Return an optional controller-provided action logger."""
    for attr_name in ("action_logger", "logger"):
        logger = getattr(controller, attr_name, None)
        if hasattr(logger, "log_action"):
            return logger
    return None

def _restore_display_mapping_frame(controller: Any, session_layer: Mapping[str, Any]) -> bool:
    """Restore the active frame display mapping from a workspace snapshot.

    Project persistence also stores per-image display mappings, but the 3-layer
    workspace snapshot should remain self-sufficient for the active view state.
    """
    raw_mapping = session_layer.get("display_mapping_frame")
    if not isinstance(raw_mapping, Mapping) or not raw_mapping:
        return False

    session_state = getattr(controller, "session_state", None)
    display_mapping = getattr(controller, "display_mapping", None)
    if session_state is None or display_mapping is None:
        return False

    try:
        active_id = int(getattr(session_state, "active_primary_id", 0))
        mapping = display_mapping.mapping_for(active_id, "frame")
        if "min" in raw_mapping or "max" in raw_mapping:
            mapping.set_window(
                float(raw_mapping.get("min", getattr(mapping, "min_val", 0.0))),
                float(raw_mapping.get("max", getattr(mapping, "max_val", 1.0))),
            )
        if "gamma" in raw_mapping:
            mapping.gamma = float(raw_mapping["gamma"])
        if "lut" in raw_mapping:
            mapping.lut = int(raw_mapping["lut"])
        if "invert" in raw_mapping:
            mapping.invert = bool(raw_mapping["invert"])
    except Exception:
        return False
    return True

def apply_workspace_snapshot_to_controller(controller: Any, snapshot: Mapping[str, Any]) -> None:
    """Restore supported workspace fields onto controller state.

    This function is best-effort and intentionally ignores invalid payloads.
    """
    logger = _get_controller_action_logger(controller)
    if logger:
        logger.log_action(
            "workspace_snapshot_applied",
            details={
                "snapshot_keys": sorted(snapshot.keys()),
                "schema": snapshot.get("schema", "unknown")
            }
        )

    session_layer = snapshot.get("session_workspace", {})
    if not isinstance(session_layer, dict):
        return

    session_state = getattr(controller, "session_state", None)
    view_state = getattr(controller, "view_state", None)
    if session_state is None or view_state is None:
        return

    applied_fields = []
    for key in ("active_primary_id", "active_support_id", "fps", "current_label"):
        if key in session_layer:
            try:
                old_val = getattr(session_state, key, None)
                setattr(session_state, key, session_layer[key])
                applied_fields.append(f"{key}:{old_val}->{session_layer[key]}")
            except Exception:
                pass

    if logger and applied_fields:
        logger.log_action(
            "workspace_layer_restored",
            details={"layer": "session", "fields": applied_fields}
        )

    if isinstance(session_layer.get("lazy_sync_groups"), Mapping):
        try:
            restored_groups = {}
            for key, value in dict(session_layer.get("lazy_sync_groups", {}) or {}).items():
                key_text = str(key)
                if key_text.startswith("builtin:"):
                    restored_key: Any = key_text
                else:
                    try:
                        restored_key = int(key_text)
                    except (TypeError, ValueError):
                        restored_key = key_text
                value_text = str(value).strip()
                if value_text:
                    restored_groups[restored_key] = value_text
            session_state.lazy_sync_groups = restored_groups
        except Exception:
            pass

    if isinstance(session_layer.get("lazy_sync_modes"), Mapping):
        try:
            restored_modes = {}
            for key, value in dict(session_layer.get("lazy_sync_modes", {}) or {}).items():
                key_text = str(key)
                if key_text.startswith("builtin:"):
                    restored_key = key_text
                else:
                    try:
                        restored_key = int(key_text)
                    except (TypeError, ValueError):
                        restored_key = key_text
                restored_modes[restored_key] = {
                    "contrast": bool(dict(value or {}).get("contrast", True)),
                    "zoom": bool(dict(value or {}).get("zoom", True)),
                    "playback": bool(dict(value or {}).get("playback", True)),
                }
            session_state.lazy_sync_modes = restored_modes
        except Exception:
            pass

    if isinstance(session_layer.get("roi_by_sync_group"), Mapping):
        try:
            session_state.roi_by_sync_group = {
                str(key): (None if value is None else dict(value))
                for key, value in dict(session_layer.get("roi_by_sync_group", {}) or {}).items()
                if str(key).strip()
            }
        except Exception:
            pass

    if isinstance(session_layer.get("feature_flags"), Mapping):
        try:
            session_state.feature_flags = {
                str(key): bool(value)
                for key, value in dict(session_layer.get("feature_flags", {}) or {}).items()
            }
        except Exception:
            pass

    if isinstance(session_layer.get("workflow_metrics"), Mapping):
        try:
            session_state.workflow_metrics = dict(session_layer.get("workflow_metrics", {}) or {})
        except Exception:
            pass

    for key in (
        "t",
        "z",
        "crop_rect",
        "tool",
        "annotate_target",
        "annotation_scope",
        "linked_zoom",
        "overlay_enabled",
        "show_ann_frame",
        "show_ann_mean",
        "profile_enabled",
        "hist_enabled",
        "hist_bins",
        "hist_region",
        "play_mode",
        "loop_playback",
    ):
        if key in session_layer:
            try:
                setattr(view_state, key, session_layer[key])
            except Exception:
                pass

    roi_rect = session_layer.get("roi_rect")
    roi_shape = session_layer.get("roi_shape")
    if roi_rect is not None and roi_shape is not None:
        try:
            view_state.roi_rect = tuple(roi_rect)
            view_state.roi_shape = str(roi_shape)
        except Exception:
            pass

    if _restore_display_mapping_frame(controller, session_layer):
        emit_display_changed(controller)
