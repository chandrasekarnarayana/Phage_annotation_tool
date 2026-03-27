# Adding A New Mutation Path

Use this checklist when introducing a new state-changing workflow.

## 1. Choose The Right Owner

Decide where the mutation belongs before writing UI code.

- If the change is persistent session/view/display state, add or extend a controller/session API.
- If the change is widget-local or canvas-artist-local, keep it in the UI/runtime layer.
- If the change is part of project load/save/apply, place it in the project/snapshot layer.

Do not start by mutating `session_state`, `view_state`, or `display_mapping` from `ui_qt`.

## 2. Add A Controller Or Session Entry Point

Create a focused mutation method in the controller/session layer.

Examples:

- `set_threshold_preview_settings(...)`
- `set_channel_display_settings_value(...)`
- `update_suggestion_decision(...)`

The method should:

- update the owned state
- emit the correct typed notifications
- keep any side effects local and explicit

## 3. Pick The Correct Notification Type

Use the most specific notification contract available.

- use `emit_view_changed(...)` for crop/ROI/tool/slice/view changes
- use `emit_display_changed(...)` for LUT/window/gamma/display mapping changes
- use `emit_annotations_changed(...)` for annotation/suggestion/metadata/batch changes
- use `emit_state_changed(...)` only for state that does not fit the typed view/display/annotation buckets

Do not emit raw controller Qt signals directly. Use `session/signal_hub.py`.

## 4. If It Uses Commands, Implement `emit_change_signals()`

For undoable commands:

- make `execute()`, `undo()`, and `redo()` perform the state change
- make `emit_change_signals()` publish the typed notification
- if the command already emits internally during execute/undo/redo, override
  `emit_change_signals()` as a no-op to avoid duplicate updates

## 5. Route GUI Reactions Through The Queued Refresh Path

If the mutation affects the visible canvas or table:

- request `_request_ui_refresh(...)` for general GUI refresh work
- use the render-specific queued path for render-heavy updates

Avoid broad synchronous redraw calls from arbitrary handlers.

## 6. Update Persistence If Needed

If the new state must survive save/load:

- add it to the project payload builder
- add it to load/apply logic
- add it to the workspace snapshot path if it is part of the 3-layer restore contract

Do not persist the same concept through two unrelated mechanisms unless that split is intentional and documented.

## 7. Add Tests

At minimum, add:

- a behavioral test for the controller/session API
- a command notification test if the change is command-based
- an architecture guard update if a new approved mutation owner is required

Useful files:

- `tests/unit/session/test_session_components.py`
- `tests/unit/session/test_command_notifications.py`
- `tests/unit/session/test_signal_hub.py`
- `tests/unit/architecture/test_ui_mutation_boundaries.py`
- `tests/unit/architecture/test_session_command_mutation_boundaries.py`

## 8. Sanity Check Before Merging

Ask these questions:

- does UI code mutate controller-owned state directly
- does the mutation emit the most specific notification type
- does the GUI react through queued refresh, not redraw sprawl
- does undo/redo preserve the same notification semantics
- does save/load restore the new state if required

If any answer is "no", the path is probably incomplete.

## Status Note

If the new path produces user-facing status:

- use the centralized status helpers such as `_status_info(...)`,
  `_status_success(...)`, `_status_warning(...)`, or `_status_error(...)`
- do not call `statusBar().showMessage(...)` directly from feature code
- do not set status-label widgets directly
- if the path represents long-running work, drive it through `ActivityStatus`
  rather than repeated informational toasts
- if the path changes compact context/metrics, make that change visible through
  derived status in `table_status.py`, not ad hoc text
