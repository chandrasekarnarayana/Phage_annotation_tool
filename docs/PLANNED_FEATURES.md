# Planned Features (Active Backlog)

Last updated: February 27, 2026

## Scope
This file tracks only not-yet-implemented capabilities.
Completed capabilities are documented in implementation summaries and test reports.

GUI design principles were checked and operationalized in the runtime UI; they are now tracked under completed cleanup items below.

## Priority Backlog

### Remaining Cleanup Backlog
No open cleanup items.

### Completed Cleanup and Unification

1. Table architecture unified to one active runtime path (dock table in `ui_setup.py` + `table_status.py`) with:
   - sortable rows
   - stack/slice scope visibility
   - direct coordinate editing
   - stable annotation identity mapping during edit/selection
2. Legacy model/panel table architecture moved out of runtime tree to docs internal archive.
3. Panel visibility synchronization expanded across major docks and centralized through shared dock action behavior.
4. Settings proxy introduced (`UnifiedSettingsProxy`) and integrated into main window settings path.
5. Actions decomposed with new feature mixins (`qc_actions.py`, `dock_actions.py`, `keyboard_events.py`).
6. Action-module decomposition completed for navigation and export/reviewer analytics:
   - `navigation_actions.py` owns jump/frame-Z command flow.
   - `export_actions.py` owns standard export and reviewer analytics dialogs.
   - `standard.py` orchestrator reduced by removing those duplicated method bodies.
7. Keyboard shortcut registry completed as single source for menu labels, help dialog rows, and event dispatch:
   - includes `F1` help mapping via action attribute binding.
   - includes collision/behavior tests for shortcut consistency.
8. Settings consolidation completion:
   - fixed `UnifiedSettingsProxy` service bridge to use framework `SettingsService` API (`get/set/remove`) with fallback compatibility.
   - added typed UI defaults + startup key migration module (`settings_schema.py`), applied during main window startup.
   - added unit tests for proxy behavior.
9. Renderer axis ownership cleanup completed for targeted helper modules; renderer-managed axes are now the active source in playback/state/threshold/ui-helper paths.
10. Runtime/docs separation applied for QC integration guide (moved under `docs/_internal`).
11. GUI design principles implementation pass completed:
   - command palette is non-modal (does not block exploration while open).
   - status bar now exposes operational context directly (dataset, T/Z frame, scope, target panel, assist trust level, QC summary, active modality, background job state, autosave state).
   - keyboard-first + review/QC paths remain exposed via command/menu/shortcut and QC issue workflows.
12. Assisted confidence visualization unification completed:
   - heuristic-only suggestions render in gray (distinct from probability semantics).
   - calibrated `p_accept` suggestions render by trust band: green (`>=0.75`), yellow (`0.5-0.75`), red (`<0.5`).
   - hover tooltip now explicitly separates `generator score` vs `Calibrated p_accept` and reports assist trust state.
13. Canvas context header overlay completed:
   - always-visible, non-interactive canvas header now surfaces annotation target and scope.
   - header updates immediately on frame/Z, target, and scope changes.
   - examples rendered include frame/mean/support context and slice-vs-stack annotation mode.
14. Progressive disclosure for advanced assist tooling completed:
   - introduced an `Advanced Analysis` dock container with grouped entry points for Explain, Training, and Calibration workflows.
   - set advanced-analysis surfaces to hidden by default to reduce onboarding clutter.
   - kept access available through dock toggles and command palette actions.
15. Command palette ranking improvements completed:
   - command ordering now blends usage frequency + recency + active workflow mode (annotate vs review).
   - hidden actions are excluded from palette results to reduce noise.
16. New `Assist Expert` layout preset completed:
   - optimizes for power users with centered canvas, visible Review Queue + Explain surfaces, QC visibility, and minimized sidebar footprint.
   - exposed in layout actions and quick-layout controls.

## Assisted Annotation Terminology

- `confidence` = calibrated `p_accept` from the ranker.
- `generator score` = heuristic score from candidate generation.
- Calibration is dataset-dependent; `p_accept` is meaningful only under similar acquisition conditions.

## Naming and Documentation Policy

- File names and docstrings use capability-oriented naming.
- Milestone labels and rollout-order labels are intentionally removed from active file names, comments, and docstrings.
- Backward compatibility comments remain focused on behavior and interfaces.
