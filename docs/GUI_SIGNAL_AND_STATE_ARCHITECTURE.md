# GUI Signal And State Architecture

This note defines the current GUI, controller, and session mutation contract for
the Qt application.

The goal is simple:

- UI code presents state and requests mutations.
- controller/session code owns persistent state changes.
- Qt signals synchronize widgets immediately.
- application events notify services and non-widget consumers.
- queued refresh helpers coalesce repaint work so the GUI stays responsive.

## Layers

The architecture is intentionally split into three cooperating layers.

1. UI layer
- Located mainly under `src/phage_annotator/ui_qt/`
- Owns widgets, canvas artists, local timers, panel state, and interaction glue
- Must not directly mutate persistent controller-owned state

2. controller/session layer
- Located mainly under `src/phage_annotator/session/`
- Owns `SessionState`, `ViewState`, display state, annotation state, undo/redo,
  project persistence, and typed mutation APIs
- Publishes Qt signals and application events through `signal_hub.py`

3. persistence/snapshot layer
- Located in `workspace_snapshot.py`, project persistence mixins, and export/load adapters
- Owns save/load/apply behavior and restore semantics across the 3-layer workspace model

## Mutation Ownership

`SessionController` is the public mutation boundary.

Rules:

- `ui_qt` modules may read controller state for presentation.
- `ui_qt` modules must mutate persistent state only through controller methods.
- session command modules may mutate state directly only when they are designated
  state-owner modules and publish the correct typed notifications.
- project persistence modules may mutate state during load/apply/restore because
  they are designated state-owner modules.

Examples of controller-owned state:

- `session_state`
- `view_state`
- `display_mapping`
- annotations, suggestions, suggestion history
- threshold, particles, channel display, SMLM, and user/session preference state

Examples of UI-owned transient state:

- debounce timers
- queued refresh flags
- temporary viewport caches
- canvas artist references
- hover/help timers

## State Ownership Contract

This contract is the anchor for the annotation workflow.

### Who Owns Truth

1. Annotation table / annotation model
- the committed annotation model is the single source of truth
- every committed annotation row must be representable in the annotation table
- persisted annotation exports and project save/load must round-trip through this model

2. Assist system
- assist is a producer of candidates, not a second truth store
- suggestions may propose rows, confidence, provenance, and conflict state
- assist must not silently overwrite committed annotations

3. UI layer
- the UI is a viewer and editor only
- widgets may request annotation mutations through controller APIs
- widgets must not directly own or mutate committed annotation collections

### Required Rule

No feature code may write directly to committed annotations without going
through the annotation model/controller boundary.

Approved write paths are limited to:
- annotation mutation helpers in `session/annotations.py`
- annotation import/replace helpers in `session/annotation_io.py`
- project/image restore paths during controlled load/reset operations
- command modules that intentionally serialize and replay annotation mutations

Everything else must call controller-owned APIs such as:
- `add_annotation(...)`
- `update_annotation(...)`
- `delete_annotations(...)`
- `replace_annotations(...)`
- context-aware controller helpers that route through those primitives

### Practical Implications

- the annotation table is not just a view; it is the operational truth surface
- assist, imports, plugins, and future DL tools must feed the same annotation model
- provenance fields such as source, status, confidence, ROI, and notes belong to
  the annotation model, not ad hoc widget state
- review actions must remain auditable because they mutate truth, not a side cache

## Notification Contracts

There are two notification channels plus one refresh queue.

### Qt Signals

Qt signals are for immediate GUI synchronization.

Current controller signal families:

- `state_changed`
- `view_changed`
- `display_changed`
- `annotations_changed`
- `playback_changed`
- `roi_changed`
- `error_occurred`

Use Qt signals when:

- widgets need to update immediately on the Qt event loop
- UI controls, tables, status text, or view-local state need to stay in sync
- the receiver is a GUI component or GUI-facing runtime helper

Qt signal emission is centralized in `src/phage_annotator/session/signal_hub.py`.
Direct raw signal emits outside that hub are treated as an architectural violation,
except for the Qt-local linked-view sync module in `session/view_sync.py`.

### Event Bus

The event bus is for cross-component and service reactions.

Use application events when:

- caches need invalidation
- non-widget services need notification
- domain reactions should not depend on widget references
- the reaction may outlive a particular window or panel instance

Examples:

- `ViewStateChangedEvent`
- `AnnotationChangedEvent`
- `CacheInvalidationEvent`

Ordering contract:

- for view changes, the Qt signal is emitted first, then the event is published
- for annotation changes, the session is marked dirty first, then the Qt signal
  is emitted, then the corresponding events are published

That ordering is covered by unit tests in `tests/unit/session/test_signal_hub.py`.

### Queued Refresh Contract

Queued refresh helpers are the third part of the flow.

They exist so repeated triggers do not force synchronous redraw storms.

Primary helpers:

- `_request_ui_refresh(...)` in `ui_qt/utils/ui_extra.py`
- `_flush_ui_refresh(...)` in `ui_qt/utils/ui_extra.py`
- `_request_render_refresh(...)` in the render path

Rules:

- GUI code should request queued refreshes instead of calling broad redraw paths directly
- multiple refresh requests should coalesce within the Qt event loop turn
- background work should publish results back through queued paths
- render-heavy work should stay on the render refresh path, not generic status/table refresh paths

## Command Notification Contract

Undoable commands must publish typed effects.

`execute_view_command(...)`, `undo_view_command(...)`, and `redo_view_command(...)`
in `session/view.py` rely on command classes to emit the correct notifications
through `emit_change_signals()`.

Command families must follow these rules:

- crop/ROI/tool/view commands emit `emit_view_changed(...)`
- display mapping commands emit `emit_display_changed(...)`
- annotation/suggestion/metadata/batch commands emit `emit_annotations_changed(...)`
- commands that already emit during their own execution/undo/redo must override
  `emit_change_signals()` as a no-op to avoid duplicate notifications
- commands must not fall back to generic `emit_state_changed(...)` unless the
  mutation is truly non-view, non-display, and non-annotation state

This behavior is covered by:

- `tests/unit/session/test_session_components.py`
- `tests/unit/session/test_command_notifications.py`

## Practical Rules For New Code

- UI handlers should request controller mutations, not edit `session_state` or `view_state` directly
- UI code should not mutate controller-owned lists or dicts through references such as
  `self.annotations`, `self.suggestions`, or `self.suggestion_history`
- new session mutation helpers should publish notifications through `signal_hub.py`
- if a change affects the canvas, prefer queued refresh helpers over direct broad redraws
- if a change affects persistence, ensure the workspace/project snapshot path restores it coherently

## Intentional Exceptions

Some direct mutations remain intentional.

- Matplotlib axes and artist objects are UI/render owned and must be mutated locally to draw
- short-lived runtime buffers and debounce state may remain outside persistent state
- persistence/apply modules may perform bulk state assignment during restore
- linked-view synchronization has a Qt-local signal path in `session/view_sync.py`

These are not considered violations because they do not represent uncontrolled
UI-to-domain mutation.

## Enforcement

Current architecture enforcement is test-backed.

- `tests/unit/architecture/test_ui_mutation_boundaries.py`
  blocks direct UI mutation of controller-owned state
- `tests/unit/architecture/test_session_command_mutation_boundaries.py`
  enforces approved session mutation roots and centralized signal emission rules
- `tests/unit/session/test_command_notifications.py`
  verifies typed command notification behavior
- `tests/unit/session/test_signal_hub.py`
  verifies signal/event ordering semantics

## Where To Look

For the canonical implementation, start with:

- `src/phage_annotator/session/signal_hub.py`
- `src/phage_annotator/session/view.py`
- `src/phage_annotator/session/commands.py`
- `src/phage_annotator/ui_qt/utils/ui_extra.py`
- `src/phage_annotator/ui_qt/actions/events.py`

## Status Architecture

The status bar is a presentation layer, not a free-form logging surface.

Implementation roots:

- `src/phage_annotator/ui_qt/services/status.py`
- `src/phage_annotator/ui_qt/services/status_derived.py`
- `src/phage_annotator/ui_qt/utils/table_status.py`
- `src/phage_annotator/ui_qt/utils/ui_docks.py`

### Source Of Truth

The status system has two distinct inputs:

1. derived status
- built from controller/session/view/job/UI runtime state
- represented as `StatusModel`
- assembled by `status_derived.py`
- used for compact bottom-bar context plus the status-details panel

2. requested message events
- represented as `StatusMessage`
- used for info/success/warning/error feedback
- may be transient or sticky

Long-running work is represented separately as `ActivityStatus`.

Feature code should request status events.
It must not manipulate status widgets directly.
Legacy `_set_status(...)` behavior is removed from the active Qt GUI path.

### Compact Bottom Bar Policy

The bottom bar is limited to three conceptual zones:

1. context
- where am I
- dataset, frame, tool, label

2. state / activity
- what is the application doing now
- ready, reviewing, saving, exporting, playback, warning, error

3. metric / alert
- what one scientific number or compact alert matters right now
- visible count, ROI area, density, freshness, QC summary, buffer health

Progress widgets appear only while an activity is active.

The status-details panel remains the expanded structured view.

### Priority Rules

Visible state selection follows this order:

1. error
2. warning
3. running activity
4. sticky advisory
5. informational/success transient
6. idle summary

This means low-priority hints do not displace warnings or active work.

### Timeout Rules

- sticky until resolved
  - unsaved changes
  - stale suggestions
  - invalid write context
- activity bound
  - loading, saving, exporting, training, assist refresh
- short
  - 1500-2500 ms
- medium
  - 3000-5000 ms
- long
  - 5000-8000 ms

### Anti-Flicker Rules

- one visible message at a time
- multiple internal items may coexist
- no rerender when the rendered signature is unchanged
- transient messages have a minimum visible duration
- high-frequency derived updates may be throttled
- playback/interactive status refresh uses throttled derived updates

### Save/Dirty Policy

Dirty state is represented as a sticky advisory, usually `Unsaved changes`.

It is derived state, not a free-text message.
Successful save/autosave may temporarily replace it with a success message.
When that success message expires, the renderer falls back to the current
derived dirty state.

### Canonical Wording

Prefer these standard phrases:

- `Ready`
- `Ready for annotation`
- `Reviewing suggestions`
- `Saving project...`
- `Exporting annotations...`
- `Suggestions stale`
- `Autosave complete`
- `QC warning`
- `Unsaved changes`

New feature code should reuse these terms instead of inventing local variants.
