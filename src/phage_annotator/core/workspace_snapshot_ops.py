"""Workspace snapshot operations: build, apply, and restore.

Definitions are split into sibling modules to keep this compatibility surface small.
"""

from phage_annotator.core.workspace_snapshot_ops_split1 import workspace_layer_registry, _path_to_str, _get_controller_action_logger, _restore_display_mapping_frame, apply_workspace_snapshot_to_controller
from phage_annotator.core.workspace_snapshot_ops_split2 import build_workspace_snapshot, extract_ui_workspace_state
