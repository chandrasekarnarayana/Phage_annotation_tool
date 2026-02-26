# Code Structure Reorganization Plan

## Current Issues

**93 loose Python files** at the root level (`src/phage_annotator/`) mixed with actual module folders.

### Root-Level Files (Needs Organization)
- Session management: 8 files
- GUI components: 20+ gui_*.py files
- ROI handling: 3 files
- SMLM processing: 4 files
- Annotation systems: 3 files
- Analysis/processing: 7 files
- Image I/O: 6 files
- Config/constants: Legacy files
- Utilities/infrastructure: 25+ files

## Proposed New Structure

```
src/phage_annotator/
├── core/                     # ✓ KEEP - Domain models
├── data/                     # ✓ KEEP - Image/data layer
├── algorithms/               # ✓ KEEP - Analysis algorithms
├── cache/                    # ✓ KEEP - Memory management
├── framework/                # ✓ KEEP - Service framework
├── io/                       # ✓ KEEP - I/O operations
├── utils/                    # ✓ KEEP - Utilities
├── ui_qt/                    # ✓ KEEP - Qt GUI (reorganize contents)
├── plugins/                  # ✓ KEEP - Plugin system
├── tools/                    # ✓ KEEP - Tools
├── config/                   # ✓ KEEP - Configuration
├── constants/                # ✓ KEEP - Constants
│
├── session/                  # NEW - Session management
│   ├── controller.py         # (from session_controller.py)
│   ├── state.py
│   ├── annotations.py        # (from session_controller_annotations.py)
│   ├── images.py
│   ├── project.py
│   ├── playback.py
│   ├── view.py
│   ├── annotation_io.py
│   ├── commands.py
│   └── __init__.py
│
├── annotation/               # NEW - Annotation subsystem
│   ├── core.py              # (from annotations.py)
│   ├── index.py
│   ├── metadata.py
│   └── __init__.py
│
├── roi/                      # NEW - ROI management
│   ├── manager.py
│   ├── interactor.py
│   ├── auto.py              # (from auto_roi.py)
│   ├── widgets.py
│   └── __init__.py
│
├── rendering/                # NEW - Visualization
│   ├── mpl.py               # (from render_mpl.py)
│   ├── orthoview.py
│   ├── scalebar.py
│   ├── lut.py               # (from lut_manager.py)
│   └── __init__.py
│
├── smlm/                     # NEW - SMLM/super-resolution
│   ├── presets.py
│   ├── thunderstorm.py
│   ├── widget.py
│   ├── ui.py
│   └── __init__.py
│
├── density/                  # NEW - Density estimation
│   ├── config.py
│   ├── model.py
│   ├── infer.py
│   └── __init__.py
│
├── deepstorm/                # NEW - DeepStorm integration
│   ├── infer.py
│   ├── widget.py
│   └── __init__.py
│
├── analysis/                 # NEW - Analysis/processing
│   ├── core.py              # (from analysis.py)
│   ├── particles.py
│   ├── threshold.py
│   ├── performance.py
│   └── __init__.py
│
├── calibration.py            # Standalone - Calibration
├── cli.py                    # Standalone - CLI
├── demo.py                   # Standalone - Demo
├── __init__.py
└── __main__.py
```

## Test Organization

```
tests/
├── unit/
│   ├── annotation/
│   │   └── test_*.py
│   ├── roi/
│   │   └── test_*.py
│   ├── session/
│   │   └── test_*.py
│   ├── smlm/
│   │   └── test_*.py
│   ├── rendering/
│   │   └── test_*.py
│   └── ...
├── integration/
│   └── test_*.py
├── performance/
│   └── test_*.py
└── conftest.py
```

## Implementation Steps

1. **Create new module folders** (empty __init__.py)
2. **Move files** to appropriate folders
3. **Update imports** in all related files
4. **Fix test imports** and reorganize test files
5. **Verify backward compatibility** with deprecated imports
6. **Run test suite** to ensure nothing breaks

## Expected Benefits

✅ **Better Organization**: Related functionality grouped logically  
✅ **Easier Navigation**: Clear module structure  
✅ **Improved Maintainability**: Reduced cognitive load  
✅ **Better Discoverability**: Clear where new features belong  
✅ **Scalability**: Foundation for future growth  

## Risk Mitigation

- Create facade imports in old locations for backward compatibility
- Create comprehensive import mapping
- Test after each major move
- Git commits for each phase

## Execution Report (2026-02-26)

### What was fixed

1. Restored broken core modules that had self-referential facades:
   - `cache/array_pool.py`
   - `cache/disk_cache.py`
   - `cache/projection_cache.py`
   - `data/pyramid.py`
   - `data/ring_buffer.py`
   - `ui_qt/rendering/export_view.py`
2. Repaired malformed package initializers with syntax errors:
   - `ui_qt/widgets/__init__.py`
   - `ui_qt/docks/__init__.py`
3. Fixed architecture/layer issues found by `scripts/check_acyclic_imports.py`:
   - Removed `algorithms -> framework` logger dependency in `algorithms/analysis.py`.
   - Reworked `framework/jobs.py` to lazy-load Qt jobs without static `framework -> ui_qt` import.
4. Repaired recursive SMLM imports:
   - Restored `smlm/widget.py` implementation.
   - Updated `ui_qt/panels/smlm.py` imports to non-recursive targets.
   - Restored `algorithms/image_processing.py` implementation.
5. Reintroduced backward-compatible root imports required by existing tests and dependent code:
   - Added facades including `array_pool.py`, `disk_cache.py`, `projection_cache.py`, `pyramid.py`, `ring_buffer.py`, `coordinate_transforms.py`, `project_io.py`, `stale_result_guard.py`, `export_view.py`, `scalebar.py`, and key GUI compatibility facades.
6. Updated test bootstrap:
   - `tests/conftest.py` now prepends `src/` to `sys.path` so local test runs do not require editable install.
7. Closed remaining unresolved internal imports:
   - Added missing compatibility modules `panels.py`, `recorder.py`, and `roi_widgets.py` so all `phage_annotator.*` imports referenced inside `src/` resolve.
8. Added hardening checks for long-term robustness:
   - New script `scripts/check_import_integrity.py` to verify:
     - no unresolved internal `phage_annotator.*` imports
     - no self-importing modules
   - Reworked `scripts/check_core_no_qt.py` to scan current headless scope (not stale file list).
   - Added `tests/test_structure_integrity.py` to enforce structural checks in pytest.

### Validation results

1. `python -m compileall -q src/phage_annotator`: passed.
2. `python -m scripts.check_core_no_qt`: passed (`Qt import guard passed.`).
3. `python scripts/check_import_integrity.py`: passed (`Import integrity passed.`).
4. `python -m scripts.check_acyclic_imports`: passed (`No layer violations found.`).
5. `pytest -ra`: passed with `261 passed, 23 skipped, 4 warnings`.

### Test-to-src audit added

1. Added `scripts/audit_test_mapping.py` to measure source module coverage from test imports.
2. Current snapshot from that script:
   - Source modules scanned: `224`
   - Modules directly referenced by tests: `20`
   - Modules without direct test imports: `204`
3. This confirms the package currently relies on compatibility/root-level test imports and still needs deeper package-level test realignment.

### Follow-up recommendation

1. Migrate remaining tests from root compatibility imports (for example `phage_annotator.projection_cache`) to canonical package paths (for example `phage_annotator.cache.projection_cache`) in phased batches.
2. Split tests into `tests/unit/<package>/` and `tests/integration/` while preserving existing markers (`gui`) and skip behavior.

## Execution Report Update (2026-02-26, Follow-up)

### Completed tasks (requested next steps 1, 2, 3, 5)

1. CI enforcement updates completed:
   - Added `python scripts/check_import_integrity.py` to CI lint job.
   - Kept `check_core_no_qt.py` and `check_acyclic_imports.py` in CI.
   - Updated stale mypy target paths in CI to current package layout.
   - Updated wheel smoke test imports to current package modules.

2. Canonical test import migration completed:
   - Migrated tests from compatibility paths to canonical package paths, including:
     - `cache.*` modules instead of root cache facades
     - `io.data.transforms` instead of root coordinate facade
     - `framework.stale_result_guard` instead of root stale-result facade
     - `ui_qt.main_window` / `ui_qt.rendering.export_view` instead of root GUI facades
     - `algorithms.*` modules instead of deprecated root analysis/auto_roi/density facades
     - `config.settings` instead of deprecated root config facade

3. Coverage-gap filling completed (high-risk packages):
   - Added `tests/test_package_internals.py` covering canonical modules in:
     - `algorithms`
     - `cache`
     - `io`
     - `framework`
   - Added concrete behavior checks (not only import smoke), including command registry execution, event metadata, cache strategy behavior, and project I/O roundtrip.

4. Warning cleanup completed:
   - Replaced internal deprecated imports of `phage_annotator.density.config` with `phage_annotator.config.density`.
   - Updated `demo.generate_dummy_image()` TIFF writes with explicit `photometric="minisblack"` and axis metadata to remove tifffile warning.
   - Remaining warnings are external (`pytz` from system packages), not project-code deprecations.

### Updated validation results

1. `python scripts/check_import_integrity.py`: passed.
2. `python scripts/check_core_no_qt.py`: passed.
3. `python scripts/check_acyclic_imports.py`: passed.
4. `pytest -ra`: passed with `266 passed, 23 skipped, 2 warnings`.
5. `scripts/audit_test_mapping.py` improvement:
   - Modules referenced by tests: increased `20 -> 24`.
   - Package-level direct coverage improved in target areas:
     - `cache`: `100.0%`
     - `algorithms`: `44.4%`
     - `framework`: `50.0%`
     - `io`: `27.3%`

## Execution Report Update (2026-02-26, Facade Phase-Out)

### Completed tasks

1. Migrated remaining internal imports away from root compatibility facades:
   - `ui_qt/main_window.py` now imports canonical modules from:
     - `cache.projection_cache`
     - `data.ring_buffer`
     - `ui_qt.panels.registry_legacy`
     - `ui_qt.panels.recorder_legacy`
   - `ui_qt/utils/ui_docks.py` now imports canonical modules from:
     - `ui_qt.panels.*`
     - `ui_qt.widgets.table_legacy`
     - `roi.widgets`
   - `ui_qt/utils/ui_setup.py` now imports `ui_qt.utils.ui_actions` / `ui_qt.utils.ui_docks` directly.
   - `ui_qt/utils/state.py` now imports `data.pyramid` directly.
   - `ui_qt/rendering/export_view.py` now imports `rendering.scalebar` directly.
   - `ui_qt/panels/performance.py` now imports `cache.array_pool` and typed ring-buffer/cache imports from canonical modules.
   - `ui_qt/controls/threshold.py` and `ui_qt/panels/threshold.py` now import `analysis.threshold`.
   - `cli.py` and `demo.py` now import `run_gui` from `ui_qt.main_window` directly.
   - logger imports were migrated to `utils.logger` in algorithms/tools/ui modules.
   - `cache/projection_cache.py` type-only imports now use `cache.disk_cache` and `config.settings`.

2. Removed obsolete root-level facade modules after import migration:
   - GUI facade family removed:
     - `gui_*`
     - `analyze_particles_panel.py`
     - `density_panel.py`
     - `performance_panel.py`
     - `threshold_panel.py`
     - `keyboard_shortcuts_dialog.py`
     - `metadata_dock.py`
     - `orthoview.py`
     - `smlm_ui.py`
     - `smlm_widget.py`
   - Data/cache/rendering facade family removed:
     - `array_pool.py`
     - `disk_cache.py`
     - `projection_cache.py`
     - `ring_buffer.py`
     - `pyramid.py`
     - `scalebar.py`
     - `export_view.py`
     - `project_io.py`
     - `stale_result_guard.py`
   - Deprecated algorithm/legacy root facades removed:
     - `auto_roi.py`
     - `calibration.py`
     - `coordinate_transforms.py`
     - `density_config.py`
     - `density_infer.py`
     - `density_model.py`
     - `particles.py`
     - `thresholding.py`
     - `analysis.py`
     - `config.py`
     - `logger.py`
     - `panels.py`
     - `recorder.py`
     - `results_table.py`
     - `roi_widgets.py`
   - Root package is now reduced to:
     - `__init__.py`
     - `__main__.py`
     - `cli.py`
     - `demo.py`

3. Updated structural guardrail for current layout:
   - `scripts/check_core_no_qt.py` headless root module list was trimmed to current root modules, removing stale facade-era entries.

### Validation results

1. `python -m compileall -q src/phage_annotator`: passed.
2. `python scripts/check_import_integrity.py`: passed.
3. `python scripts/check_core_no_qt.py`: passed.
4. `python scripts/check_acyclic_imports.py`: passed.
5. `pytest -ra`: passed with `266 passed, 23 skipped, 2 warnings`.
6. `python scripts/audit_test_mapping.py`:
   - Source modules scanned: `164` (reduced from `224` after facade cleanup).
   - Modules referenced by tests: `24`.

## Execution Report Update (2026-02-26, Steps 1/2/3/4 Completed)

### Completed tasks

1. Added structural guardrails for the post-facade package layout:
   - Added `scripts/check_package_layout.py` to enforce:
     - allowed root modules only: `__init__.py`, `__main__.py`, `cli.py`, `demo.py`
     - required package directories and `__init__.py` presence
     - legacy root facade modules stay removed
   - Added this check to CI lint workflow.
   - Added `test_package_layout_script_passes()` in structure integrity tests.
   - Added missing `src/phage_annotator/constants/__init__.py` and package exports.

2. Reorganized tests into source-aligned directories:
   - Created and populated:
     - `tests/unit/annotation/`
     - `tests/unit/algorithms/`
     - `tests/unit/cache/`
     - `tests/unit/framework/`
     - `tests/unit/io/`
     - `tests/unit/rendering/`
     - `tests/unit/package/`
     - `tests/unit/structure/`
     - `tests/integration/`
     - `tests/integration/gui/`
     - `tests/performance/`
   - Updated test tooling to support recursive structure:
     - `scripts/audit_test_mapping.py` now scans `tests/**/test_*.py`.
   - Removed stale CI path ignore that referenced old test location.

3. Added focused coverage for requested gap areas:
   - Added `tests/unit/analysis/test_analysis_modules.py`
     - covers `analysis.core`, `analysis.particles`, `analysis.threshold`
   - Added `tests/unit/roi/test_roi_manager.py`
     - covers ROI manager copy/template/json operations and `roi.auto` export
   - Added `tests/unit/constants/test_settings_constants.py`
     - covers `constants.settings` defaults and `constants` package re-exports
   - Added `tests/unit/session/test_session_components.py`
     - covers session image-state shaping, session command undo/redo serialization,
       `session.state` facade behavior, and `session.view` state mutation methods
   - Made session package headless-safe:
     - `session/__init__.py` now handles missing Qt bindings gracefully and still exports `SessionState`.

4. Documentation/comment hygiene pass completed in high-noise modules:
   - Simplified verbose migration-era doc/comments in:
     - `src/phage_annotator/constants/settings.py`
     - `src/phage_annotator/ui_qt/main_window.py`
     - `src/phage_annotator/ui_qt/utils/ui_setup.py`
     - `src/phage_annotator/ui_qt/utils/ui_docks.py`
   - Kept behavior-relevant comments while removing long roadmap/phase narrative blocks.

### Updated validation results

1. `python -m compileall -q src/phage_annotator`: passed.
2. `python scripts/check_package_layout.py`: passed.
3. `python scripts/check_import_integrity.py`: passed.
4. `python scripts/check_core_no_qt.py`: passed.
5. `python scripts/check_acyclic_imports.py`: passed.
6. `pytest -ra`: passed with `280 passed, 24 skipped, 2 warnings`.
7. `python scripts/audit_test_mapping.py`:
   - Modules referenced by tests: `24 -> 36`.
   - Requested package coverage now:
     - `analysis`: `100.0%`
     - `constants`: `100.0%`
     - `roi`: `50.0%`
     - `session`: `44.4%`
