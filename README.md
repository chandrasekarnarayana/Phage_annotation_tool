# Phage Annotator

Phage Annotator is a Qt + Matplotlib microscopy annotation IDE for 2D/3D/time TIFF workflows, with assistive suggestion review, reproducible project persistence, and dock-based expert UX.

## Quick Start

```bash
python -m venv .venv-phage
source .venv-phage/bin/activate
pip install -e .[dev,cache]
phage-annotator --demo
```

For Fiji bridge backends, install optional dependencies:

```bash
pip install -e .[fiji]
```

### Offline / Air-gapped Install

If your environment cannot reach package indexes:

```bash
python -m pip install -U pip setuptools wheel
python -m pip install -e . --no-build-isolation
```

## Current Capabilities

- Central multi-view canvas for stack/projection annotation.
- VS Code-style dock architecture with panel switcher and layout presets.
- Annotation table + review queue + explain panel workflows.
- Assisted suggestions with heuristic and calibrated `p_accept` semantics.
- Undo/redo, command palette, keyboard-first review (`A/R/N/P`, etc.).
- Project save/load with schema migration support.
- Annotation import/export (legacy CSV, ThunderSTORM CSV parse, JSON).
- QC issue detection and navigation.
- Selectable ThunderSTORM backends (`internal`, `fiji_subprocess`, `fiji_pyimagej`).
- SMLM parity CLI (`phage-annotator-smlm-parity`) for internal-vs-Fiji comparisons.
- SMLM preflight CLI (`phage-annotator-smlm-preflight`) for runtime readiness checks.
- SMLM demo-run CLI (`phage-annotator-smlm-run-demo`) for deterministic smoke tests.
- Fiji plugin toolkit CLI (`phage-annotator-fiji-plugin-tool`) for manifest onboarding.

See [Current Capabilities](/home/cs/Desktop/Phage_annotation_tool/docs/CURRENT_CAPABILITIES.md) for detailed, versioned feature status.

## Production Validation Commands

```bash
.venv-phage/bin/python -m pytest -q
QT_QPA_PLATFORM=offscreen .venv-phage/bin/python -m pytest -m gui --run-gui
```

See [Production Readiness Checklist](/home/cs/Desktop/Phage_annotation_tool/docs/PRODUCTION_READINESS_CHECKLIST.md).

## Documentation

- [Current Capabilities](/home/cs/Desktop/Phage_annotation_tool/docs/CURRENT_CAPABILITIES.md)
- [Planned Features](/home/cs/Desktop/Phage_annotation_tool/docs/PLANNED_FEATURES.md)
- [Fiji ThunderSTORM Bridge](/home/cs/Desktop/Phage_annotation_tool/docs/FIJI_THUNDERSTORM_BRIDGE.md)
- [SMLM Reproducibility Runbook](/home/cs/Desktop/Phage_annotation_tool/docs/SMLM_REPRODUCIBILITY_RUNBOOK.md)
- [Panel Architecture Reference](/home/cs/Desktop/Phage_annotation_tool/docs/PANEL_ARCHITECTURE_REFERENCE.md)
- [Reports Index](/home/cs/Desktop/Phage_annotation_tool/docs/reports/README.md)

## Notes

- Fiji bridge mode executes JAR plugins through Fiji/ImageJ; configure executable + macro in the SMLM panel.
- If a CLI entrypoint is not found, reinstall in the active environment: `python -m pip install -e .`
- For release hygiene, generated artifacts (`*.egg-info`) and large demo binaries are intentionally not tracked.
