# Planned Features (Active Backlog)

Last updated: March 2, 2026

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
17. Suggestion freshness/staleness guardrails completed:
   - tracks suggestion generation age and edit-after-generation staleness.
   - surfaces stale state in status bar, review queue, and canvas diagnostics.
   - blocks bulk accept actions when stale (with explicit regenerate guidance).
18. Assisted confidence terminology/semantics clarification completed:
   - UI now uses `Acceptance likelihood (p_accept)` wording for calibrated ranker output.
   - tooltips explicitly state this predicts user acceptance behavior, not ground-truth correctness.
19. Modality/evidence control and calibration diagnostics completed:
   - added status-bar active modality selector and canvas modality/projection context text.
   - added layer-style `Modality Layers` panel (visibility, opacity, colormap, role) with preset save/load.
   - added calibration visualizer (reliability-style p_accept bin vs observed acceptance).
20. Effective assist context unification completed:
   - added immutable `Effective Assist Context` line (strategy, modality/evidence preset, projection, scope, target, stale/fresh state).
   - mirrored this line in both status bar and Review Queue header context line.
21. Stale bulk-accept safety override completed:
   - stale bulk-accept remains safety-gated by default.
   - added explicit one-shot confirmation path in batch preview (`Accept stale suggestions for this batch only`).
22. Always-visible assist color semantics legend completed:
   - Review Queue now includes persistent legend for heuristic gray + acceptance-likelihood bands.
23. Assist context-delta messaging completed:
   - when strategy/preset/projection changes after suggestion generation, concise context-delta notice is emitted in transient status and queue subtext.
24. Inline review throughput telemetry completed:
   - Review Queue now shows accepted/min, rejected/min, and seconds/decision for active review sessions.
25. Quick compare mode for layer presets completed:
   - added one-click A/B layer preset compare in Modality Layers + Assist action entry.
   - compare now preserves current camera limits during toggles.
26. Mini calibration sparkline completed:
   - compact reliability sparkline surfaced in Review Queue for lightweight calibration awareness.
27. Panel-aware first-run snippets completed:
   - short first-run contextual hints added for Review Queue, Modality Layers, and Calibration surfaces.
28. Session-level assist change log completed:
   - strategy/preset/projection/scope/target context changes are recorded with timestamps for reproducibility and audit/export pipelines.
29. GUI expectation contract operationalization completed (from `GUI_EXPECTATION_SPEC.md`):
   - canvas-first defaults and Focus Canvas behavior implemented with real space reclaim.
   - explicit always-visible operational state in status bar maintained (dataset, T/Z, scope, target, assist, QC/results).
   - progressive disclosure + mode-aware docks implemented (annotate/review/inspect right-dock behavior).
   - dynamic context-aware view/target controls implemented with invalid-choice disabling and explanatory hints.
   - long-hover micro-help implemented for high-risk/high-ambiguity controls.
   - bottom task panel behavior simplified to Results/QC/Diagnostics with auto-collapse when empty.
   - enforcement moved to GUI integration tests for state-level expectation checks.
   - specification doc removed after implementation consolidation to avoid drift.
30. Interactive auto-open policy toast hardened and completed:
   - inline `Pin` / `Disable auto-open` actions remain available directly in the toast.
   - lifecycle stabilized for GUI teardown to prevent callback-related crashes.
31. System diagnostics surfaces fully unified into a single `System` dock:
   - Logs/Diagnostics, Performance, and Recorder now share one dock widget with internal tabs.
   - panel switching routes to the same dock and selects the correct tab.
32. Dock flash refinement completed with tabbar-driven pulse:
   - tabified docks now use dedicated `QTabBar` flash animation path.
   - non-tabified docks retain deterministic fallback highlight.
33. Production-readiness hardening completed:
   - full GUI suite pass verified in venv/headless mode (`-m gui --run-gui`).
   - full repository test pass verified in venv.
   - optional disk-cache tests now dependency-aware (skip when `zstandard` is unavailable).
   - release checklist added under `docs/PRODUCTION_READINESS_CHECKLIST.md`.

## Assisted Annotation Terminology

- `confidence` = calibrated `p_accept` from the ranker.
- `generator score` = heuristic score from candidate generation.
- Calibration is dataset-dependent; `p_accept` is meaningful only under similar acquisition conditions.

## Naming and Documentation Policy

- File names and docstrings use capability-oriented naming.
- Milestone labels and rollout-order labels are intentionally removed from active file names, comments, and docstrings.
- Backward compatibility comments remain focused on behavior and interfaces.
