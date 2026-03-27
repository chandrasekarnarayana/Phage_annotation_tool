# Workspace State 3-Layer Model

This project now supports a centralized 3-layer workspace snapshot model for exact save/load workflows.

## Core Module

- `src/phage_annotator/core/workspace_snapshot.py`

Primary API:

- `build_workspace_snapshot(controller, settings_preferences)`
- `apply_workspace_snapshot_to_controller(controller, snapshot)`
- `workspace_layer_registry()`

Schema ID:

- `workspace_snapshot.v1`

## Layer 1: Project File Layer

Tracked keys:

- `project_path`
- `project_save_time`
- `dirty`
- `last_folder`
- `recent_images`
- `image_count`
- `annotation_counts`

## Layer 2: Session/Workspace Layer

Tracked keys:

- `active_primary_id`
- `active_support_id`
- `fps`
- `current_label`
- `labels`
- `t`
- `z`
- `crop_rect`
- `roi_rect`
- `roi_shape`
- `tool`
- `annotate_target`
- `annotation_scope`
- `linked_zoom`
- `overlay_enabled`
- `show_ann_frame`
- `show_ann_mean`
- `profile_enabled`
- `hist_enabled`
- `hist_bins`
- `hist_region`
- `play_mode`
- `loop_playback`
- `annotation_space`
- `generation_space`
- `display_mapping_frame`
- `ui_workspace`

`ui_workspace` stores UI-level state captured at project save:

- panel visibility maps
- annotation panel visibility map
- canvas layout rows/cols
- active layout preset
- sidebar collapsed/expanded flags
- sidebar stack index
- window geometry/state payloads (base64)

## Layer 3: Settings/Preferences Layer

Tracked keys:

- `values`
- `defaults`

Notes:

- `defaults` mirrors `phage_annotator.constants.settings.DEFAULTS`.
- `values` stores save-time settings payload.

## Centralized Signal Triggering

Core signal helper:

- `src/phage_annotator/session/signal_hub.py`

Canonical signal names:

- `state_changed`
- `view_changed`
- `display_changed`
- `annotations_changed`
- `playback_changed`
- `error_occurred`
- `roi_changed`

Helpers:

- `emit_controller_signal(controller, signal_name, *args)`
- `emit_state_changed(controller)`
- `emit_view_changed(controller, ...)`
- `emit_display_changed(controller)`
- `emit_playback_changed(controller)`
- `emit_roi_changed(controller)`
- `emit_error(controller, message)`
- `emit_annotations_changed(controller, image_id=None, change_type="modified")`

The annotation helper emits both:

- Qt controller signal (`annotations_changed`)
- Event bus event (`AnnotationChangedEvent`)

## Save/Load Integration

Project save now includes:

- `settings.workspace_snapshot`
- `settings.workspace_layer_registry`

Project load now restores:

- session/view values via `apply_workspace_snapshot_to_controller(...)`
- snapshot/registry payloads on `session_state` for inspection
- UI workspace via `extract_ui_workspace_state(...)` and `_restore_ui_workspace_state(...)`

This enables full workspace reconstruction to evolve from one canonical model.
