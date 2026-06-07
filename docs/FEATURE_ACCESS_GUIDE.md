# Feature Access Guide

This guide lists the main capabilities and the usual way to access them from
the GUI or command line.

## Startup And Environment

- Launch GUI: `phage-annotator`
- Alternate launch: `python -m phage_annotator.cli`
- Create conda environment: `conda env create -f project/environment.yml`
- Runtime environment check: performed automatically before GUI startup.
- Runtime memory/worker policy: configured from `project/runtime.spec.yml` and
  implemented in `phage_annotator.runtime`.

Environment overrides:

```bash
PHAGE_ANNOTATOR_MAX_WORKERS=2 PHAGE_ANNOTATOR_CACHE_MB=2048 phage-annotator
```

## Image Loading And Workspace

- Open image stacks from startup: `phage-annotator -i image1.tif -i image2.tif`
- Open image stacks from GUI: File/Open actions in the main window.
- Demo image: launch with no input files; the CLI creates a synthetic TIFF.
- Workspace save/load: project persistence actions in the File menu.
- Autosave/recovery: project recovery flow runs through the session layer.

Supported workflow areas:

- TIFF and OME-TIFF stack reading.
- 2D, Z-stack, and time-series axis normalization.
- Project schema migration.
- Recent files and workspace state restoration.

## Annotation

- Add point annotation: choose annotation tool, then click on the canvas.
- Delete/edit annotation: use annotation table, context menu, or tool commands.
- Annotation table: docked table panel in the GUI.
- Labels and taxonomy: annotation controls and metadata workflows.
- Import/export: File and export actions for CSV, JSON, and standard exports.

Keyboard-oriented review workflows include undo/redo, navigation shortcuts, and
assist review shortcuts such as accept/reject/next/previous.

## Assisted Annotation

- Generate suggestions: Assist menu or assist panel actions.
- Review suggestions: review queue panel and suggestion explain panel.
- Accept/reject suggestions: buttons in the review panel or keyboard shortcuts.
- Strategy controls: assist strategy controls in the GUI.
- Training controls: assist training/preference controls.
- QC-aware review: suggestion filtering and QC issue navigation.

See `docs/ASSIST_GUIDE.md` for more detailed assist workflows.

## Multi-Modality And Display

- Add modalities/projections: lazy loader and channel controls.
- Switch active modality: modality controls and panel selectors.
- Synchronize views: linked zoom/playback/contrast sync controls.
- Adjust contrast/LUT: display and contrast controls.
- Projection selection: projection selector and display controls.
- Scale bar and overlays: display/rendering controls.

The display stack is split across data mapping, rendering, Qt panels, and session
sync modules so numerical behavior stays separate from GUI wiring.

## ROI And Analysis

- Draw or update ROI: ROI controls and canvas interactions.
- Auto ROI: ROI proposal actions from the ROI/analysis workflow.
- Crop and profile views: ROI crop/profile controls.
- Particle analysis: particles/analyze panels.
- Threshold analysis: threshold panel and threshold controls.
- Density and DeepSTORM analysis: density/deepstorm panels when configured.

## SMLM And Fiji/ThunderSTORM

- SMLM panel: configure and run SMLM workflows from the GUI.
- Internal ThunderSTORM-style backend: selectable backend option.
- Fiji subprocess/PyImageJ backends: optional bridge dependencies and external
  plugin manifests.
- Preflight CLI: `phage-annotator-smlm-preflight`
- Parity CLI: `phage-annotator-smlm-parity`
- Demo CLI: `phage-annotator-smlm-run-demo`
- Fiji plugin toolkit: `phage-annotator-fiji-plugin-tool`

Related docs:

- `docs/FIJI_THUNDERSTORM_BRIDGE.md`
- `docs/FIJI_PLUGIN_MANIFEST_SDK.md`
- `docs/SMLM_REPRODUCIBILITY_RUNBOOK.md`

## Quality Control

- QC issue detection: QC actions and background validation.
- QC thresholds: QC thresholds panel and configuration guide.
- QC issue navigation: QC issues panel.
- QC export: standard QC export helpers.

Related docs:

- `docs/QC_THRESHOLDS_CONFIGURATION_GUIDE.md`
- `docs/BACKGROUND_QC_MONITORING.md`

## Performance And Responsiveness

- Background jobs: routed through job services instead of blocking the UI.
- Cache budgets: controlled by runtime policy and GUI preferences.
- Projection cache: keeps repeated rendering/analysis work bounded.
- Array pooling and zero-copy utilities: reduce avoidable memory churn.
- Performance panel: GUI view into job/cache/runtime status.
- Performance tests: `tests/performance/`.

## Developer And Maintenance Commands

```bash
python scripts/check_root_cleanliness.py
python scripts/check_package_layout.py
python scripts/check_source_quality.py
python scripts/check_import_integrity.py
python scripts/check_core_no_qt.py
python scripts/check_markdown_quality.py
python scripts/check_release_hygiene.py
python scripts/generate_source_reference.py
python -m pytest -q
```

Generated source reference:

- `docs/SOURCE_REFERENCE.md`
