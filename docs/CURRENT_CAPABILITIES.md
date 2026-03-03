# Current Capabilities

Last updated: March 2, 2026

## GUI and Workflow

- Dock-based panel architecture with constrained left/right primary rails.
- Unified panel opening path via panel manager (`open_panel` orchestration).
- Panel switcher available from command palette and `Panels: Open Panel…` (`Ctrl+Alt+P`).
- Focus-canvas and layout presets for annotate/analyze/assist workflows.
- Right-dock segmented review surfaces (table, queue, explain).

## Assisted Annotation

- Heuristic proposal generation + optional learned ranking.
- Calibrated acceptance likelihood (`p_accept`) semantics in UI.
- Explicit stale-suggestion guarding for bulk accept paths.
- Suggestion review telemetry and context visibility in status/review surfaces.

## SMLM Interoperability

- ThunderSTORM backend selection:
  - `internal` native pipeline
  - `fiji_subprocess` headless Fiji bridge
  - `fiji_pyimagej` PyImageJ bridge
- External Fiji plugin discovery from `external_plugins/` with plugin selector (multi-JAR support).
- Strict manifest SDK for plugin invocation (typed params, validation, arg builders, macro-template generation).
- Runtime preflight checks (UI + CLI) for Fiji bridge readiness.
- `plugins.config` metadata parsing from plugin JARs for command/menu enrichment.
- Optional Fiji bridge dependencies (`pyimagej`, `jpype1`) are available via `pip install .[fiji]`.
- CLI parity harness available at `phage-annotator-smlm-parity`.
- Reproducibility runbook mode:
  - lockable SMLM profiles
  - provenance event capture
  - runbook bundle export for replay/audit

## Persistence and I/O

- Project save/load with schema versioning and migration (`schema_version` + migration path).
- Annotation import parsers for:
  - legacy `x,y` CSV
  - ThunderSTORM CSV format
  - JSON
- Annotation export:
  - CSV
  - JSON
  - project/session persistence.

## Quality and Validation

- Core unit/integration tests (`pytest -q`) in CI.
- GUI integration tests in headless CI lane (`-m gui --run-gui`).
- Release hygiene guards:
  - oversized tracked file guard
  - generated artifact guard
  - markdown quality guard.
