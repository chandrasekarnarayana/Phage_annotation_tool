## Code Quality Audit

Date: 2025-02-14

This audit covers `src/phage_annotator` with emphasis on GUI architecture, rendering, state management, and scientific correctness.

### Line Counts

| File | Lines |
| --- | ---: |
| `gui_actions.py` | 822 |
| `gui_rendering.py` | 667 |
| `gui_ui_setup.py` | 631 |
| `gui_state.py` | 625 |
| `gui_controls_smlm.py` | 610 |
| `render_mpl.py` | 602 |
| `gui_controls_threshold.py` | 574 |
| `gui_controls_display.py` | 543 |
| `gui_ui_extra.py` | 486 |
| `ui_docks.py` | 425 |
| `gui_export.py` | 424 |
| `gui_mpl.py` | 319 |
| `roi_interactor_mpl.py` | 316 |
| `analysis.py` | 314 |
| `gui_events.py` | 288 |
| `session_controller_annotation_io.py` | 263 |
| `smlm_thunderstorm.py` | 255 |
| `deepstorm_infer.py` | 244 |
| `gui_table_status.py` | 238 |
| `jobs.py` | 237 |
| `gui_controls_density.py` | 214 |
| `thresholding.py` | 214 |
| `session_controller_project.py` | 212 |
| `density_infer.py` | 211 |
| `annotation_metadata.py` | 206 |
| `io.py` | 199 |
| `threshold_panel.py` | 194 |
| `gui_roi_crop.py` | 190 |
| `gui_controls_roi.py` | 188 |
| `annotations.py` | 185 |
| `gui_jobs.py` | 184 |
| `density_model.py` | 181 |
| `orthoview.py` | 172 |
| `ring_buffer.py` | 171 |
| `session_controller_view.py` | 171 |
| `io_annotations.py` | 169 |
| `session_controller_images.py` | 169 |
| `metadata_dock.py` | 167 |
| `smlm_widget.py` | 165 |
| `metadata_reader.py` | 163 |
| `gui_controls_preferences.py` | 160 |
| `particles.py` | 152 |
| `export_view.py` | 146 |
| `display_mapping.py` | 142 |
| `gui_controls_results.py` | 137 |
| `analyze_particles_panel.py` | 135 |
| `ui_actions.py` | 131 |
| `deepstorm_widget.py` | 125 |
| `tools.py` | 124 |
| `session_controller_annotations.py` | 122 |
| `density_panel.py` | 119 |
| `gui_annotations.py` | 117 |
| `projection_cache.py` | 117 |
| `gui_playback.py` | 113 |
| `session_controller.py` | 113 |
| `session_state.py` | 113 |
| `project_io.py` | 108 |
| `annotation_index.py` | 94 |
| `roi_manager.py` | 91 |
| `smlm_presets.py` | 88 |
| `recorder.py` | 82 |
| `results_table.py` | 76 |
| `scalebar.py` | 76 |
| `gui_image_io.py` | 72 |
| `smlm_ui.py` | 69 |
| `logger.py` | 58 |
| `panels.py` | 55 |
| `roi_widgets.py` | 51 |
| `cli.py` | 47 |
| `pyramid.py` | 45 |
| `calibration.py` | 44 |
| `lut_manager.py` | 44 |
| `demo.py` | 42 |
| `session_controller_playback.py` | 36 |
| `image_processing.py` | 35 |
| `image_models.py` | 34 |
| `config.py` | 32 |
| `gui_controls_recorder.py` | 30 |
| `__init__.py` | 29 |
| `gui_constants.py` | 28 |
| `density_config.py` | 27 |
| `gui_controls.py` | 26 |
| `gui_debug.py` | 14 |
| `__main__.py` | 7 |

### Responsibilities (High-Level)

- `gui_controls.py`: Main UI handlers (preferences, SMLM, thresholding, particle analysis, density inference, ROI manager, display mapping).
- `session_controller.py`: Session orchestration, project/image state, view/display state, signals.
- `gui_actions.py`: File/menu actions; project load/save; recent images; annotations import/export.
- `gui_rendering.py`: Rendering pipeline, projections, overlays, pyramids, hist/profile updates.
- `gui_ui_setup.py`: Main window layout, widgets, docks, menu wiring.
- `gui_state.py`: Shared UI state + helpers (zoom, mapping, coordinate transforms, cache/pyramid helpers).
- `render_mpl.py`: Matplotlib renderer, overlay artists, export rendering.
- `ui_docks.py`: Panel registry and dock construction.
- Core logic: `analysis.py`, `io.py`, `annotations.py`, `project_io.py`, `projection_cache.py`, `ring_buffer.py`, `pyramid.py`.

### Top 10 Architectural Risks

1) **Monolithic GUI modules** (`gui_controls.py`, `session_controller.py`): difficult to reason about ownership and side effects.
2) **Implicit coupling** across mixins (heavy reliance on `self.<attr>` presence and order).
3) **Threading boundaries**: job callbacks are mostly safe, but not uniformly guarded against stale updates.
4) **ROI/crop/display coordinate transforms** are scattered across UI and rendering layers.
5) **Duplicate ROI logic** (ROI manager vs ROI selection; multiple ROI overlays).
6) **State mutation from multiple entry points** (UI + controller + mixins).
7) **Logging consistency**: not all modules use the structured logger; error boundary not unified.
8) **Long-running tasks** not uniformly cancelled or throttled (some manual background jobs).
9) **Project schema evolution** is handled, but warnings are not consistently surfaced to the UI.
10) **Render pipeline** combines data prep + artist updates; difficult to unit test.

### Standards Violations (Current)

- **File size**: `gui_controls.py` and `session_controller.py` exceed 1000 lines.
- **Docstrings**: several public functions/classes lack NumPy-style docstrings, especially in GUI mixins.
- **PEP8/typing**: a number of public interfaces are missing full type hints.
- **Implicit coupling**: helpers assume presence of many `self` attributes.
- **Core/Qt boundary**: some non-GUI modules are clean, but enforcement is not automated.
- **Error boundaries**: missing unified GUI-thread exception hook in some entrypoints.

### Completed Splits (This Pass)

1) `gui_controls.py` (2395 lines) → modularized into:
   - `gui_controls_display.py`: display mapping, LUT, gamma/log, auto-contrast.
   - `gui_controls_density.py`: density model/panel wiring.
   - `gui_controls_threshold.py`: threshold tool + analyze particles.
   - `gui_controls_smlm.py`: SMLM runs + exports.
   - `gui_controls_roi.py`: ROI manager dialog + ROI measurements.
   - `gui_controls_results.py`: results table interactions.
   - `gui_controls_preferences.py`: preferences dialog + QSettings save.
   - `gui_controls_recorder.py`: recorder UI and persistence.

2) `session_controller.py` (1133 lines) → modularized into:
   - `session_state.py`: dataclasses for session/view/display/image state.
   - `session_controller_images.py`: image loading, axis interpretation, metadata.
   - `session_controller_view.py`: view/display setters (ROI, crop, LUT, tool, etc.).
   - `session_controller_playback.py`: playback state.
   - `session_controller_annotations.py`: annotation edits + undo/redo.
   - `session_controller_annotation_io.py`: annotation IO/indexing/merge.
   - `session_controller_project.py`: project load/save + recovery.

### Immediate Remediation Plan

- Split oversized files with minimal API changes by using mixin subclasses.
- Add module docstrings and NumPy docstrings for all public API entry points.
- Consolidate GUI-thread exception hook and job error logging.
- Add CI guard for Qt imports in core modules.
- Add unit tests in `tests/` for axis handling, annotations import, ROI masks, cache eviction, density count logic.
