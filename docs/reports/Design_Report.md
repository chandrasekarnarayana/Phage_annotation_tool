# Design Report

## Document Control
| Field | Value |
|---|---|
| Project | Phage Annotation Tool |
| Document Version | 0.2-draft |
| Report Date | 2026-02-27 |
| Intended Audience | Software reviewers, contributors, developers, JOSS reviewers |
| Primary Repository Path | `src/phage_annotator/` |
| Related Documents | `docs/ARCHITECTURE_DETAILED.md`, `docs/dev/feature_control_matrix.md`, `docs/PLANNED_FEATURES.md`, `docs/reports/Technical_Appendix.md`, `docs/reports/Reproducibility_and_Validation.md` |

## How to Use This Report
- This file is the reviewer-facing architecture and design narrative.
- Claims are written to be traceable to current code paths and executable checks.
- Validation boundaries are explicit; unvalidated or blocked areas are called out.

## 1. Executive Summary
Status: Complete

### 1.1 Tool Purpose
Phage Annotator is a desktop microscopy annotation application for TIFF/OME-TIFF data. It targets 2D/3D/time stacks and provides interactive keypoint annotation, modality-aware display control, and integrated analysis workflows in a Qt + Matplotlib interface.

### 1.2 Core Capabilities
- Axis standardization to `(T, Z, Y, X)` with OME-first interpretation and 3D fallback heuristics.
- Lazy image metadata loading and memmap-friendly data handling for large TIFF stacks.
- Session-centric state model (`SessionController`) with explicit view/display/annotation mutation paths.
- Modality system with `ModalitySpec`, projection choices, and sync managers for view/playback behavior.
- Project save/load to `.phageproj`, per-image annotation sidecars, and autosave/recovery files.
- Analysis features for thresholding, particle analysis, ROI statistics, and intensity-window auto-calculation.

### 1.3 High-Level Architecture Summary
Runtime starts in `cli.py`, creates a framework `ApplicationContext`, then launches `ui_qt/main_window.py`. The GUI composes mixins for actions, controls, rendering, jobs, and export. `SessionController` centralizes mutable session state and emits signals consumed by the GUI. Algorithm modules (`algorithms/`, `analysis/`) are designed as Qt-free computation units. Caching (`cache/projection_cache.py`) and background jobs (`ui_qt/services/jobs.py`) reduce UI stalls for projection-heavy and I/O-heavy operations.

### 1.4 Review-Relevant Claims
- C-001: Package layout and import integrity checks pass in this environment.
- C-002: Core modality/sync/annotation logic has direct unit-test evidence.
- C-003: Display mapping sync rules are implemented and serializable.
- C-004: Full Qt-dependent validation is currently blocked in this environment.
- C-005: Some legacy compatibility surfaces exist and include schema/attribute drift risks.
- C-006: Current licensing/citation state is not yet JOSS-ready.

## 2. Statement of Need
Status: Complete

### 2.1 Problem Definition
Microscopy workflows require precise, repeatable annotation and view control across multi-dimensional image stacks, while retaining enough session state to resume work and reproduce visual/analysis context.

### 2.2 Existing Gaps
- Ad hoc scripts and one-off viewers often do not preserve full interactive state across sessions.
- Multi-modality synchronization and panel-specific display mappings are typically fragmented across tools.
- Reviewer-facing traceability between implementation and validation is often missing.

### 2.3 Intended User Groups
- Experimental researchers using microscopy workflows.
- Software developers extending or maintaining the tool.
- Reviewers evaluating architecture quality and reproducibility.

### 2.4 Impact and Expected Outcomes
- Faster annotation and review loops via integrated visualization and analysis controls.
- Reduced state-loss risk via project save/load and recovery artifacts.
- Improved reviewability via explicit requirement-to-code/test traceability.

## 3. Scope and Non-Goals
Status: Complete

### 3.1 In-Scope Features
- GUI-based annotation and visualization (`src/phage_annotator/ui_qt/`).
- Session state control and mutation signaling (`src/phage_annotator/session/controller.py`).
- TIFF/OME-TIFF metadata and axis standardization (`src/phage_annotator/io/readers/base.py`).
- Project persistence with sidecar annotations (`src/phage_annotator/io/projects/base.py`, `src/phage_annotator/session/project.py`).
- Modality abstractions and synchronization managers (`src/phage_annotator/session/modality.py`, `src/phage_annotator/session/view_sync.py`, `src/phage_annotator/session/multi_playback.py`).
- Projection caching and memory-budgeted eviction telemetry (`src/phage_annotator/cache/projection_cache.py`).

### 3.2 Out-of-Scope Features
- Headless batch processing as a first-class workflow (current entry point launches GUI).
- Full CI-grade GUI validation in this runtime (blocked by missing Qt bindings).
- Formal ADR corpus (no ADR files currently maintained).

### 3.3 Assumptions and Constraints
- Python `>=3.9` (from `pyproject.toml`), Qt bindings required for GUI.
- Local filesystem access for image/project/annotation files.
- Optional dependencies alter capability surface (for example `pytest-benchmark`, `psutil`, skimage/scipy fallback behavior).

## 4. Requirements and Quality Attributes
Status: Complete

### 4.1 Functional Requirements
| ID | Requirement | Priority | Verification Method |
|---|---|---|---|
| FR-001 | Standardize image arrays to `(T,Z,Y,X)` with metadata-aware logic | High | `tests/unit/io/test_io_axes.py`, `tests/unit/io/test_io.py` |
| FR-002 | Centralize mutable session state behind `SessionController` | High | `tests/unit/session/test_session_components.py` |
| FR-003 | Support dynamic modality definitions and serialization | High | `tests/unit/session/test_modality_system.py` |
| FR-004 | Support display mapping sync rules and serialization | High | `tests/unit/data/test_sync_rules.py`, `tests/integration/test_sync_propagation_integration.py` |
| FR-005 | Persist projects, mappings, ROIs, and annotation paths | High | Code path audit + `tests/unit/test_modality_persistence.py` |
| FR-006 | Import/export annotations as CSV/JSON with compatibility support | High | `tests/unit/annotation/test_annotations_roundtrip.py` |
| FR-007 | Provide non-blocking background job execution for heavy operations | Medium | Code path audit (`ui_qt/services/jobs.py`) |
| FR-008 | Provide threshold and particle analysis workflows | Medium | `tests/unit/analysis/test_analysis_modules.py` |
| FR-009 | Cache projections with LRU + budget enforcement | Medium | `tests/unit/cache/test_projection_cache_modality.py` |
| FR-010 | Enforce package structure/import guards | Medium | `tests/unit/structure/test_structure_integrity.py` + scripts |

### 4.2 Non-Functional Requirements
| ID | Attribute | Requirement | Measurement |
|---|---|---|---|
| NFR-001 | Reliability | Core non-Qt logic should pass targeted tests | 129 tests passed across executed subsets (see Section 11) |
| NFR-002 | Responsiveness | Long-running tasks should be asynchronous from GUI thread | Job manager + projection job paths reviewed; end-to-end GUI not validated in this runtime |
| NFR-003 | Maintainability | Package remains modular and import-safe | `check_import_integrity.py`, `check_core_no_qt.py`, `check_package_layout.py` pass |
| NFR-004 | Portability | Headless modules import without Qt | `test_non_gui_modules_import_cleanly` passed |
| NFR-005 | Reproducibility | Validation commands and blockers must be explicit | Reproducibility report includes exact commands and errors |

### 4.3 Traceability Matrix
| Requirement ID | Implementation Path(s) | Test Path(s) | Notes |
|---|---|---|---|
| FR-001 | `src/phage_annotator/io/readers/base.py` | `tests/unit/io/test_io_axes.py` | Includes OME-aware branch and heuristic fallback |
| FR-003 | `src/phage_annotator/session/modality.py` | `tests/unit/session/test_modality_system.py` | Covers add/remove/rename/serialize |
| FR-004 | `src/phage_annotator/data/display_mapping.py` | `tests/unit/data/test_sync_rules.py` | Covers sync flags and roundtrip |
| FR-005 | `src/phage_annotator/io/projects/base.py`, `src/phage_annotator/session/project.py` | `tests/unit/test_modality_persistence.py`, `tests/unit/session/test_state_persistence.py` | Partial coverage: modality persistence tests pass; Qt-dependent state persistence remains blocked |
| FR-007 | `src/phage_annotator/ui_qt/services/jobs.py` | No direct unit test found | See technical debt item TD-001 |
| FR-009 | `src/phage_annotator/cache/projection_cache.py` | `tests/unit/cache/test_projection_cache_modality.py` | LRU/budget behavior covered |
| FR-010 | `scripts/check_*.py` | `tests/unit/structure/test_structure_integrity.py` | Verifies structure and non-Qt import policy |

## 5. System Context and Architecture
Status: Complete

### 5.1 Context Diagram
```text
User (researcher/developer)
  -> CLI (`phage-annotator`) or GUI menus
  -> Qt Main Window (`ui_qt/main_window.py`)
  -> SessionController (`session/controller.py`)
  -> Algorithms/Analysis (`algorithms/`, `analysis/`)
  -> I/O and Project Storage (`io/`, `.phageproj`, CSV/JSON)
  -> Caches and Jobs (`cache/projection_cache.py`, `ui_qt/services/jobs.py`)
```

### 5.2 Layered Architecture
| Layer | Responsibility | Primary Paths |
|---|---|---|
| Entry | CLI parsing and application context bootstrapping | `src/phage_annotator/cli.py` |
| Presentation | Qt widgets, actions, controls, rendering orchestration | `src/phage_annotator/ui_qt/` |
| Session Control | Authoritative mutable state and signaling | `src/phage_annotator/session/controller.py` + mixins |
| Domain/Data | Session dataclasses, display mappings, image models | `src/phage_annotator/core/`, `src/phage_annotator/data/` |
| Compute | Projection, thresholding, particle/ROI analytics | `src/phage_annotator/algorithms/`, `src/phage_annotator/analysis/` |
| Persistence | Metadata read, annotations, project save/load | `src/phage_annotator/io/`, `src/phage_annotator/session/project.py` |
| Infrastructure | Event/log/settings services, plugin manager | `src/phage_annotator/framework/` |

### 5.3 Module Boundary Summary
| Module | Responsibility | Key Files |
|---|---|---|
| CLI | User entry point, input validation, demo launch | `src/phage_annotator/cli.py` |
| UI | Menus, docks, controls, rendering, dialogs | `src/phage_annotator/ui_qt/main_window.py` |
| Session | Image/view/playback/annotation/project mutation paths | `src/phage_annotator/session/controller.py` |
| Data | Display mapping and image metadata containers | `src/phage_annotator/data/display_mapping.py`, `src/phage_annotator/data/models.py` |
| Algorithms | Numerical operations with Qt-free interfaces | `src/phage_annotator/algorithms/analysis.py`, `src/phage_annotator/analysis/threshold.py` |
| Cache | Projection cache with telemetry and optional disk layer | `src/phage_annotator/cache/projection_cache.py` |
| Framework | Application context and service abstractions | `src/phage_annotator/framework/context.py`, `src/phage_annotator/framework/plugin.py` |

## 6. Data Model and State Management
Status: Complete

### 6.1 Core Domain Entities
| Entity | Purpose | Source |
|---|---|---|
| `LazyImage` | Lightweight metadata + lazy array holder for one image | `src/phage_annotator/data/models.py` |
| `SessionState` | Persistent project/session state | `src/phage_annotator/core/session_state.py` |
| `ViewState` | Active view/crop/ROI/tool state | `src/phage_annotator/core/session_state.py` |
| `DisplayMapping` | Non-destructive intensity transform + sync rules | `src/phage_annotator/data/display_mapping.py` |
| `Keypoint` | Annotation record schema for CSV/JSON roundtrip | `src/phage_annotator/core/annotation.py` |
| `ModalitySpec` | Modality identity, projection mode, display defaults | `src/phage_annotator/session/modality.py` |

### 6.2 Session State Lifecycle
1. Session creation: `SessionController.__init__` builds `SessionState`, `ViewState`, and base mappings.
2. Runtime mutations: UI invokes controller methods (`set_t`, `set_roi`, `add_annotation`, `set_display_mapping`, etc.).
3. Save: export mixin composes settings and calls `SessionProjectMixin.save_project`.
4. Load: `SessionProjectMixin.load_project` rebuilds images, mappings, annotations, and selected settings.
5. Recovery: autosave timer in `main_window.py` triggers `.recovery/*.annotations.json` snapshots.

### 6.3 Display Mapping and Synchronization Rules
- Canonical mapping fields are `min_val`, `max_val`, `gamma`, `mode`, `lut`, `invert`.
- Sync controls are `sync_vmin`, `sync_vmax`, `sync_contrast` and are serialized by `mapping_to_dict`.
- `propagate_sync_updates` computes target `(image_id, panel)` pairs for mapped panels with sync enabled.
- Per-image/per-panel mappings are lazily allocated via `mapping_for(image_id, panel)`.

### 6.4 Backward Compatibility and Migration
- `session/migration.py` upgrades legacy primary/support state to `ModalityManager` with `migration_version` tagging.
- Multiple facade modules preserve older import paths (for example `analysis/core.py` re-exporting algorithms).
- Compatibility is partly code-level and partly convention-based; some legacy surfaces now show attribute drift (see TD table).

## 7. Interaction and Control Flow Design
Status: Complete

### 7.1 Main User Workflows
1. Open images: menu action in `ui_qt/actions/file.py` -> metadata read -> controller image registration -> refresh.
2. Annotate points: mouse/tool event -> `SessionAnnotationsMixin.add_annotation` -> undo push + signal -> redraw.
3. Adjust display: control change in `ui_qt/controls/display.py` -> mapping update -> optional sync -> render update.
4. Run analysis: threshold/particle/density controls submit job manager tasks and apply results asynchronously.
5. Persist work: export/project actions write annotations/project payload and update dirty state.

### 7.2 Event Wiring and Handlers
- UI signal wiring is centralized in `ui_qt/actions/events.py` and setup mixins.
- Session emits `state_changed`, `view_changed`, `display_changed`, `annotations_changed`, `playback_changed`.
- Job signals (`job_started`, `job_progress`, `job_result`, `job_error`) feed status/log widgets through `JobsMixin`.

### 7.3 Synchronization Flows
- View sync: `ViewSyncManager` supports zoom/pan/T/Z/crop sync and optional link groups.
- Playback sync: `ModalityPlaybackManager` supports synchronized, independent, and sequential modes.
- Contrast sync: `DisplayMapping` sync flags drive cross-panel propagation decisions.

## 8. Algorithmic and Numerical Design
Status: Complete

### 8.1 Projection and Summary Computation
- `compute_projections` supports `mean/std/min/max` and axis modes `tz`, `t`, `z`.
- Projection results are normalized to `float32` for display and caching efficiency.
- UI state layer schedules projection jobs and uses LOD fallback while full-resolution computation runs.

### 8.2 Threshold and Analysis Pathways
- Thresholding uses skimage methods when available with fallback behavior (`analysis/threshold.py`).
- Postprocessing supports area filtering, morphology open/close, hole fill, and optional watershed split.
- Particle analysis computes area/perimeter/circularity/centroids/bounds and can exclude edge-touching objects.

### 8.3 Numerical Stability and Data Type Handling
- Auto-window uses percentile bounds and swaps endpoints if needed.
- Log display mode uses `log1p` transform in normalization builder to avoid zero instability.
- Empty-array paths return safe defaults (`0.0/1.0`, `nan`, or empty arrays depending on function contract).

## 9. Performance and Scalability
Status: Partial

### 9.1 Performance-Critical Paths
- Projection computation and repeated view refresh.
- Large-TIFF reads and contiguous playback block access.
- Overlay composition and histogram sampling on large arrays.

### 9.2 Caching and Memory Strategy
- Projection cache uses LRU with MB budget and telemetry counters.
- Pyramid entries are tracked separately and evicted before primary projections.
- Optional disk cache hooks and modality-aware byte tracking are implemented.

### 9.3 Background Jobs and Responsiveness
- Job execution is based on `QThreadPool` with cooperative cancellation tokens.
- Projection and analysis jobs include stale-generation guards before applying results.
- Known gap: GUI code calls `jobs.cancel(job_id)` and `jobs.active_job_count()` but these methods are not present on current `ui_qt/services/jobs.py::JobManager`.

### 9.4 Benchmark Summary
| Scenario | Metric | Baseline | Current | Notes |
|---|---|---|---|---|
| `standardize_axes` perf test | benchmark runtime | Not established | Not measured | `tests/performance/test_perf.py` skipped (missing `pytest-benchmark`) |
| B/C microbench module | benchmark runtime | Not established | Not measured | Bench tests exist, but Qt/plugin prerequisites not met in this environment |
| Projection cache modality tests | pass/fail | n/a | Pass | Behavior correctness validated in unit tests, not throughput-benchmarked |

## 10. Reliability, Errors, and Recovery
Status: Complete

### 10.1 Failure Modes
- Missing image files at project load.
- Invalid/partial annotation import payloads.
- Missing Qt runtime or backend in test/runtime environments.
- Optional dependency absence changing algorithm backend behavior.

### 10.2 Error Handling Policy
- User-facing failures are surfaced via dialogs/status/log widgets in UI mixins.
- Background job exceptions are captured and emitted as `job_error` signals.
- Project save uses temp-file + backup replacement pattern for safer writes.

### 10.3 Recovery and Autosave
- Autosave timer interval: 120 seconds.
- Recovery artifacts are written to `.recovery/` adjacent to project files.
- Recovery prompt restores newer annotation snapshots relative to project save time.

## 11. Validation and Verification
Status: Complete (bounded)

### 11.1 Test Strategy
- Unit tests for core/session/algorithms/cache/io modules.
- GUI/integration tests gated behind Qt availability and `--run-gui` marker policy.
- Structure scripts for import integrity and package layout checks.

### 11.2 Current Validation Snapshot
Executed in this audit:
- `pytest tests/unit/session/test_modality_system.py tests/unit/data/test_sync_rules.py tests/unit/annotation/test_multi_modality_annotations.py`
  - Result: `92 passed`
- `pytest tests/unit/structure/test_structure_integrity.py`
  - Result: `4 passed`
- `pytest tests/unit/session/test_session_components.py`
  - Result: `5 passed`
- `pytest tests/unit/test_modality_persistence.py`
  - Result: `10 passed`
- `pytest tests/unit/io/test_io_axes.py tests/unit/algorithms/test_projection.py tests/unit/cache/test_projection_cache_modality.py`
  - Result: `18 passed`
- `python scripts/check_import_integrity.py`
  - Result: passed
- `python scripts/check_core_no_qt.py`
  - Result: passed
- `python scripts/check_package_layout.py`
  - Result: passed

Blocked/partial in this audit:
- `pytest --collect-only -q` reported 13 collection errors in Qt-dependent modules due missing Qt binding support (`PyQt5.sip` / Qt backend import failures).
- `pytest tests/performance/test_perf.py` skipped due missing `pytest-benchmark`.

### 11.3 Validation Gaps
- End-to-end Qt GUI behavior could not be validated in this runtime.
- No measured performance baseline or regression threshold report produced in this audit.
- Job cancellation API coverage is absent despite runtime call sites.

## 12. Reproducibility and Packaging
Status: Partial

### 12.1 Environment Specification
See `docs/reports/Reproducibility_and_Validation.md` for exact environment and command records.

### 12.2 Determinism and Data Provenance
- Core transformation and serialization logic is deterministic for fixed inputs.
- Performance tests often use random arrays and should be seeded for strict reproducibility if metric baselines are introduced.

### 12.3 Installation and Runtime Constraints
- Runtime dependencies are declared in `pyproject.toml`.
- GUI operation and a large subset of tests require Qt bindings.
- Optional dependencies alter benchmark and advanced analysis availability.

## 13. Security and Safety Considerations
Status: Partial

### 13.1 Input Validation and File Safety
- CLI validates input paths via Click (`exists=True`, `readable=True`).
- Project save uses backup and atomic replace mechanics.
- Export paths and annotation parsing include explicit format/field checks in multiple paths.

### 13.2 Dependency and Supply-Chain Considerations
- Optional dependency fallbacks reduce hard failures but can change algorithm implementation path.
- No formal SBOM or dependency-audit artifact is included in this report set.

## 14. Extensibility and Maintainability
Status: Complete

### 14.1 Extension Points
- Plugin framework (`framework/plugin.py`) with entry-point discovery.
- UI modularity via mixins, panel registry, and scoped control modules.
- Session migration utilities for backward-compatible schema evolution.

### 14.2 Design Decisions and Trade-offs
- Qt + Matplotlib chosen for interactive desktop control and familiarity.
- Session-centric mutation model improves coherence but introduces broad controller responsibilities.
- Backward-compatibility facades lower migration friction but increase drift risk if not aggressively pruned.

### 14.3 Technical Debt Register
| ID | Debt Item | Impact | Mitigation Plan |
|---|---|---|---|
| TD-001 | `JobManager` API mismatch (`cancel`, `active_job_count` called but not implemented) | Runtime errors in cancel/status paths | Add missing API methods and unit tests for cancellation/status behavior |
| TD-002 | Legacy attribute drift in metadata/dedup paths (`view_state.roi`, `mapping.vmin`, `kp.x_px`) | Potential runtime failures on specific feature toggles/import paths | Normalize to canonical fields (`roi_spec`, `min_val/max_val`, `x/y`) and add regression tests |
| TD-003 | Qt imports in session modules block collection in non-Qt env | Reduced portability and CI flexibility | Introduce Qt abstraction or guard imports for headless testability |
| TD-004 | Performance evidence is mostly structural, not benchmarked | Harder to assess scalability claims | Add reproducible benchmark suite with thresholds in CI |
| TD-005 | License/citation state not aligned with common JOSS expectations | External review/release risk | Add explicit citation metadata and align licensing policy with target publication venue requirements |

## 15. JOSS Review Mapping
Status: Partial

| JOSS Expectation | Section(s) in This Report | Supporting Artifact |
|---|---|---|
| Statement of need | Section 2 | `README.md`, this report |
| Functionality description | Sections 1, 5, 7, 8 | `src/phage_annotator/` modules |
| Documentation quality | Sections 1-17 | `docs/` + report pack |
| Tests and validation | Section 11 | `tests/`, structure check scripts |
| Reproducibility | Section 12 | `docs/reports/Reproducibility_and_Validation.md` |
| Licensing and citation clarity | Section 14, this row | Current status: partial; citation metadata and publication alignment still pending |

## 16. Limitations and Roadmap
Status: Complete

### 16.1 Current Limitations
- Full GUI validation blocked without Qt runtime in this environment.
- Some compatibility-era modules or code paths are not fully harmonized with current core dataclasses.
- Performance tests exist but were not executed to produce stable baseline numbers here.

### 16.2 Near-Term Roadmap
1. Resolve TD-001/TD-002 compatibility drift issues and add direct tests.
2. Stand up a Qt-enabled validation environment and execute GUI-marked suites.
3. Produce reproducible benchmark baselines for projection, cache, and UI-latency paths.
4. Finalize citation metadata and publication-oriented documentation artifacts.

## 17. Conclusion
The codebase shows a substantial, modular implementation with strong evidence for core non-Qt logic and structure integrity. The primary readiness blockers for external software review are environment-complete GUI validation, a small but important set of compatibility drift issues, and missing benchmark/citation maturity for publication-grade reproducibility narratives.

## Appendix A. Figures and Tables Index
- No figures embedded in this draft.
- Tables: requirements, NFRs, traceability, module boundaries, technical debt, JOSS mapping.

## Appendix B. Source-to-Claim Index
| Claim ID | Claim | Source File/Test/Benchmark |
|---|---|---|
| C-001 | Import/layout integrity checks pass | `scripts/check_import_integrity.py`, `scripts/check_core_no_qt.py`, `scripts/check_package_layout.py` |
| C-002 | Core modality/sync logic validated | `tests/unit/session/test_modality_system.py`, `tests/unit/data/test_sync_rules.py` |
| C-003 | Modality annotation utilities validated | `tests/unit/annotation/test_multi_modality_annotations.py` |
| C-004 | Qt validation blocked in current runtime | `pytest --collect-only -q` (Qt import errors) |
| C-005 | Projection cache modality behavior validated | `tests/unit/cache/test_projection_cache_modality.py` |
| C-006 | Job API mismatch exists | `src/phage_annotator/ui_qt/utils/jobs.py`, `src/phage_annotator/ui_qt/services/jobs.py` |
