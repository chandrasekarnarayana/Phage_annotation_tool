# Technical Appendix

## Document Control
| Field | Value |
|---|---|
| Project | Phage Annotation Tool |
| Document Version | 0.2-draft |
| Report Date | 2026-02-27 |
| Companion Report | `docs/reports/Design_Report.md` |

## 1. Repository and Module Inventory
Status: Complete

### 1.1 Top-Level Package Inventory
Observed in this workspace:
- Python source files under `src/phage_annotator`: `221`
- Test files matching `tests/**/test_*.py`: `53`

| Package/Module | Python File Count | Primary Purpose |
|---|---:|---|
| `ui_qt` | 103 | Qt presentation layer, controls, rendering, dialogs |
| `io` | 16 | Metadata reading, axis normalization, project I/O |
| `session` | 15 | Session controller, state mutation mixins, modality/sync managers |
| `data` | 10 | Display mapping, image models, state data sources |
| `algorithms` | 10 | Qt-free numerical operations |
| `framework` | 9 | Application context, services, plugin interfaces |
| `analysis` | 4 | Facades/wrappers around algorithm modules |
| `cache` | 5 | Projection cache, disk cache interfaces, memory helpers |
| `annotation` | 4 | Annotation compatibility facade and exports |
| `core` | 4 | Dataclass domain models (`SessionState`, `Keypoint`) |
| `roi` | 5 | ROI models and widget manager |
| `rendering` | 5 | Matplotlib renderer abstractions |
| `density` | 4 | Density-model interfaces and config |
| `smlm` | 5 | SMLM pipeline structures |
| `deepstorm` | 3 | DeepSTORM integrations |
| `tools` | 4 | Tool/registry abstractions |
| `config` | 3 | App/runtime settings |
| `constants` | 2 | Settings and constants |
| `plugins` | 1 | Plugin namespace package |
| Root modules (`cli.py`, `demo.py`, `__init__.py`, `__main__.py`) | 4 | Entry points and package exports |

### 1.2 UI Submodule Inventory
| Submodule | Python File Count | Purpose |
|---|---:|---|
| `ui_qt/utils` | 31 | UI setup, state adapters, export helpers, job wiring |
| `ui_qt/controls` | 19 | Display/threshold/density/SMLM user controls |
| `ui_qt/panels` | 17 | Dock/panel widgets, performance UI |
| `ui_qt/widgets` | 9 | Reusable UI components |
| `ui_qt/actions` | 8 | Menu/action wiring and callbacks |
| `ui_qt/rendering` | 5 | Rendering mixins, LUT management |
| `ui_qt/services` | 4 | Job manager + service adapters |
| `ui_qt/dialogs` | 3 | Interactive dialogs |
| `ui_qt/registry`, `ui_qt/docks`, `ui_qt/handlers` | 4 total | Panel registry, dock assembly, keyboard handlers |

## 2. Interface and Contract Specifications
Status: Complete

### 2.1 Session Controller Contract
| Aspect | Contract |
|---|---|
| Ownership | Session mutations are expected to flow through `SessionController` and mixins (`session/controller.py`). |
| Signals | Emits `state_changed`, `view_changed`, `display_changed`, `annotations_changed`, `playback_changed`, `roi_changed`, `error_occurred`. |
| Data roots | Holds `SessionState`, `ViewState`, and root `DisplayMapping`. |
| Persistence boundary | Delegates persistence to `SessionProjectMixin` and `io/projects/base.py`. |

### 2.2 Display Mapping Contract
| Aspect | Contract |
|---|---|
| Window state | Canonical fields are `min_val`, `max_val`; updated via `set_window()`. |
| Transform state | `gamma`, `mode`, `lut`, `invert` define normalization/color mapping behavior. |
| Sync state | `sync_vmin`, `sync_vmax`, `sync_contrast`, `set_sync_rules()`, `propagate_sync_updates()`. |
| Scope model | Root mapping has `per_panel` and `per_image` submaps keyed by `(image_id, panel)`. |
| Serialization | `mapping_to_dict()` / `mapping_from_dict()` preserve sync flags and display fields. |

### 2.3 Modality Contract
| Aspect | Contract |
|---|---|
| Identity | `ModalitySpec.idx` is unique/stable within manager lifetime. |
| Source link | `ModalitySpec.image_id` maps modality to loaded image. |
| Projection | `projection_type` enum supports `raw`, `mean`, `std`, `min`, `max`. |
| Display defaults | `ModalityDisplaySettings` carries modality-level defaults (`vmin/vmax/lut/gamma/projection_axis`). |
| Serialization | `ModalitySpec.to_dict/from_dict`, `ModalityManager.to_dict/from_dict`. |

### 2.4 Job Manager Contract
| Aspect | Contract |
|---|---|
| Execution model | `QThreadPool` + `QRunnable` with signal-based callbacks. |
| Cancellation model | Cooperative cancellation through `CancelToken`. |
| Current public methods | `submit(...)`, `cancel_all()`. |
| Known mismatch | UI paths call `jobs.cancel(job_id)` and `jobs.active_job_count()` but these methods are not present in current `JobManager` implementation. |

## 3. State Transition Tables
Status: Complete

### 3.1 Contrast Update Transition
| Trigger | Precondition | State Change | Side Effect |
|---|---|---|---|
| B/C slider/spin change | Image is loaded and active mapping exists | Update `DisplayMapping.min_val/max_val/gamma` | Redraw + possible sync propagation |
| Auto-contrast action | Sample data available | Compute percentile window and apply to selected panels | Redraw, optional async computation |
| LUT/invert toggle | LUT set available | Update `lut`/`invert` in mapping | Redraw and display-state persistence |

### 3.2 Project Load Transition
| Step | Action | Failure Handling |
|---|---|---|
| Parse `.phageproj` | `io.projects.base.load_project` reads payload | Load dialog on parse/type errors |
| Resolve image entries | `read_metadata` per image path | Missing files accumulated and shown as warning |
| Restore mappings and ROIs | Deserialize per-image maps | Invalid entries skipped/fallback defaults |
| Restore session settings | Assign indices/config/settings fields | Partial restore tolerated; load may still succeed |

### 3.3 Annotation Import Transition
| Step | Action | Failure Handling |
|---|---|---|
| Detect format | CSV/JSON and legacy/ThunderSTORM detection | Unsupported formats raise and are surfaced |
| Parse and map image IDs | Map by image name or fallback target image | Unknown names remapped to active/forced image |
| Merge/deduplicate | Merge into per-image annotation lists | Dedup path has known legacy-field risk (see Section 8) |
| Mark dirty + emit | Set session dirty and emit `annotations_changed` | UI dialog used for hard parse failures |

### 3.4 Recovery Transition
| Step | Action | Failure Handling |
|---|---|---|
| Autosave tick | Save recovery JSON in `.recovery/` when dirty project exists | If disabled/not dirty/no project path, no-op |
| Recovery probe | Find newest recovery newer than project save time | No candidate => no-op |
| User decision | Prompt restore confirmation | Decline => no-op |
| Apply recovered points | Map by image name and replace per-image lists | Errors surface in critical dialog |

## 4. Serialization and Compatibility
Status: Complete

### 4.1 Project Payload Fields (Current)
| Field Group | Source |
|---|---|
| Core project envelope (`tool`, `version`, `schema_version`) | `io/projects/base.py` |
| Image entries (`path`, `annotations`, `interpret_3d_as`) | `io/projects/base.py` |
| Per-image display mappings | `session/project.py` + `mapping_to_dict()` |
| ROI, threshold, particle configs | `io/projects/base.py`, `session/project.py` |
| Annotation import history | `io/projects/base.py`, `session/annotation_io.py` |
| Optional modality manager payload | `io/projects/base.py` (`modality_manager`) |

### 4.2 Compatibility and Persistence Gaps
| Gap | Observed Location | Risk |
|---|---|---|
| View sync state (`ViewSyncManager.to_dict`) not persisted in project save settings | `ui_qt/utils/export.py`, `session/project.py` | Cross-session sync setup loss |
| Multi-playback state (`ModalityPlaybackManager.to_dict`) not persisted in project save settings | same | Playback mode/FPS/loop group loss |
| Metadata helper uses legacy field names (`view_state.roi`, `mapping.vmin`, `mapping.lut_name`) | `session/project.py::build_annotation_metadata` | Potential runtime errors when metadata filename encoding is enabled |
| Annotation dedup fallback references `kp.x_px/y_px` for `Keypoint` schema that uses `x/y` | `session/annotation_io.py::_dedup_annotations` | Potential import/dedup failures on code paths requiring fallback branch |

## 5. Algorithm Notes
Status: Complete

### 5.1 Projection Selection
- `compute_projections()` supports `mean/std/min/max` and axis modes (`tz`, `t`, `z`).
- UI state layer (`ui_qt/utils/state.py`) builds projection cache keys with modality and crop context.
- LOD strategy returns pyramid fallback while full-resolution projection job is still running.

### 5.2 Contrast Mapping
- Auto-window uses percentile bounds (`compute_auto_window`).
- `DisplayMapping.build_norm()` selects normalize/log/gamma behavior.
- Sync policies are explicit flags, serialized with mappings, and surfaced in tests.

### 5.3 Threshold and Particle Analysis
- Threshold methods include manual + auto families, with skimage-based methods when available.
- Mask postprocessing includes size filtering, morphology, hole filling, optional watershed split.
- Particle measurements include geometric descriptors and optional contour extraction.

### 5.4 Annotation Modality Helpers
- `core/multi_modality.py` implements filter/propagate/assign/summary helpers.
- Global annotations (`modality_idx=None`) are optionally visible across modalities.

## 6. Performance and Runtime Internals
Status: Partial

### 6.1 Cache and Runtime Responsibilities
| Component | Role |
|---|---|
| `ProjectionCache` | LRU memory cache for projections and pyramid levels, with telemetry and optional disk hooks |
| `FrameRingBuffer` / `BlockPrefetcher` | Playback-oriented contiguous frame buffering |
| Job system (`ui_qt/services/jobs.py`) | Moves expensive work off GUI thread with signal callbacks |
| Debounce timers | Prevent recursive redraw loops during async projection completion |

### 6.2 Performance Instrumentation Snapshot
- Existing benchmark tests depend on `pytest-benchmark` and/or Qt runtime.
- `tests/performance/test_perf.py` skipped in this environment (`pytest-benchmark` absent).
- No numeric throughput/latency baseline was generated in this audit.

## 7. Test Inventory and Evidence
Status: Complete (bounded)

### 7.1 Executed Tests in Current Audit
| Command | Outcome |
|---|---|
| `pytest tests/unit/session/test_modality_system.py tests/unit/data/test_sync_rules.py tests/unit/annotation/test_multi_modality_annotations.py` | `92 passed` |
| `pytest tests/unit/structure/test_structure_integrity.py` | `4 passed` |
| `pytest tests/unit/session/test_session_components.py` | `5 passed` |
| `pytest tests/unit/test_modality_persistence.py` | `10 passed` |
| `pytest tests/unit/io/test_io_axes.py tests/unit/algorithms/test_projection.py tests/unit/cache/test_projection_cache_modality.py` | `18 passed` |
| `python scripts/check_import_integrity.py` | passed |
| `python scripts/check_core_no_qt.py` | passed |
| `python scripts/check_package_layout.py` | passed |

### 7.2 Non-Executed / Blocked Groups
| Test Group | Blocker |
|---|---|
| Qt-heavy unit/integration tests | Missing Qt binding support (`PyQt5.sip`, Qt backend import failures) |
| Benchmark suites | Missing `pytest-benchmark` plugin and/or Qt runtime |

### 7.3 Additions Recommended Before External Review
- Add direct unit tests for `ui_qt/services/jobs.JobManager` cancellation/status APIs.
- Add regression tests for metadata/dedup code paths with current `Keypoint` and `ViewState` schemas.
- Add reproducible benchmark thresholds with fixed seeds and environment capture.

## 8. Failure Mode Catalog
Status: Complete

| Failure Mode | Detection | Mitigation | Residual Risk |
|---|---|---|---|
| Missing image files in project load | Existence checks and load warnings | Partial load + warning dialog | Session may restore incompletely |
| Qt runtime not available | Import-time failure during test collection/runtime startup | Documented prerequisites; marker-gated GUI tests | GUI validation blocked in some environments |
| Job cancellation calls missing API | Runtime exception on cancel/status paths | Pending code fix (TD-001) | User-visible failure in cancel workflow |
| Legacy field-name drift in compatibility paths | Runtime exception when those paths execute | Pending normalization + tests (TD-002) | Hidden until specific settings/workflows trigger |
| Missing benchmark plugin | Benchmark tests skipped | Install dev extras and rerun | No quantitative performance baseline |

## 9. ADR Index (Architecture Decision Records)
Status: Partial

No formal ADR files were found in `docs/` during this audit. Decision rationale currently lives in code comments, tests, and phase-oriented documents.

## 10. Traceability Addendum
| Artifact Type | Path |
|---|---|
| Main design report | `docs/reports/Design_Report.md` |
| Reproducibility guide | `docs/reports/Reproducibility_and_Validation.md` |
| Architecture snapshot | `docs/ARCHITECTURE_DETAILED.md` |
| Feature matrix snapshot | `docs/dev/feature_control_matrix.md` |
| Planned work snapshot | `docs/PLANNED_FEATURES.md` |
