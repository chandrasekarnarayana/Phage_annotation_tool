"""Core panel/dock management aggregator — re-exports all panel helpers."""

from __future__ import annotations

from phage_annotator.ui_qt.utils.panel_helpers import (
    _panel_auto_open_key,
    _panel_pinned_key,
    _panel_auto_open_trigger_key,
    _is_auto_reason,
    _auto_trigger_from_reason,
    _is_user_intent_reason,
    _show_status_message,
    _hide_auto_open_toast,
    _show_auto_open_toast,
    _merge_system_docks,
    _select_system_tab_for_panel,
    _iter_unique_dock_specs,
)
from phage_annotator.ui_qt.utils.dock_panel_registry_impl import (
    _find_tab_for_dock,
    _init_panel_auto_policy_state,
    refresh_panel_policy_actions,
    is_panel_auto_open_enabled,
    is_panel_auto_open_enabled_for_trigger,
    set_panel_auto_open_enabled,
    set_panel_auto_open_enabled_for_trigger,
    is_panel_pinned,
    set_panel_pinned,
)
from phage_annotator.ui_qt.utils.dock_panel_init_chunk1 import (
    init_panels,
    get_panel_spec,
    get_dock,
)
from phage_annotator.ui_qt.utils.dock_panel_init_chunk2 import (
    _apply_panel_constraints,
    _canonical_area_for_panel,
    _tabify_group_for_panel,
)
from phage_annotator.ui_qt.utils.dock_panel_create import (
    apply_panel_defaults,
    create_dock,
    wire_dock_action,
)
from phage_annotator.ui_qt.utils.dock_panel_manager_impl import build_panel_registry
from phage_annotator.ui_qt.utils.dock_panel_manager import (
    PanelManager,
    _panel_manager,
    open_panel,
    _flash_dock,
)

__all__ = [
    "_panel_auto_open_key", "_panel_pinned_key", "_panel_auto_open_trigger_key",
    "_is_auto_reason", "_auto_trigger_from_reason", "_is_user_intent_reason",
    "_show_status_message", "_hide_auto_open_toast", "_show_auto_open_toast",
    "_merge_system_docks", "_select_system_tab_for_panel", "_iter_unique_dock_specs",
    "_find_tab_for_dock", "_init_panel_auto_policy_state", "refresh_panel_policy_actions",
    "is_panel_auto_open_enabled", "is_panel_auto_open_enabled_for_trigger",
    "set_panel_auto_open_enabled", "set_panel_auto_open_enabled_for_trigger",
    "is_panel_pinned", "set_panel_pinned",
    "init_panels", "get_panel_spec", "get_dock",
    "_apply_panel_constraints", "_canonical_area_for_panel", "_tabify_group_for_panel",
    "apply_panel_defaults", "create_dock", "wire_dock_action",
    "build_panel_registry",
    "PanelManager", "_panel_manager", "open_panel", "_flash_dock",
]
