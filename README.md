# Phage Annotator

Phage Annotator is a Qt + Matplotlib microscopy annotation IDE for 2D/3D/time TIFF workflows, with assistive suggestion review, reproducible project persistence, and dock-based expert UX.

## Clone

```bash
git clone https://github.com/<your-org-or-user>/phage-annotator.git
cd phage-annotator
```

## Local Install

### Linux / macOS

```bash
python -m venv .venv-phage
source .venv-phage/bin/activate
python -m pip install --upgrade pip
python -m pip install -e .[dev,cache]
```

### Windows (PowerShell)

```powershell
python -m venv .venv-phage
.venv-phage\Scripts\Activate.ps1
python -m pip install --upgrade pip
python -m pip install -e .[dev,cache]
```

### Conda / Mamba

```bash
conda env create -f project/environment.yml
conda activate phage-annotator
python -m pip install -e .
```

The application checks `project/environment.yml` at startup and prints environment
warnings before the GUI launches if required runtime packages are missing or too
old.

### Optional Fiji bridge dependencies

```bash
python -m pip install -e .[fiji]
```

### Offline / Air-gapped Install

If your environment cannot reach package indexes:

```bash
python -m pip install -U pip setuptools wheel
python -m pip install -e . --no-build-isolation
```

## Run

```bash
phage-annotator
```

If the entrypoint command is not found:

```bash
python -m phage_annotator.cli
```

## Verify Install

```bash
phage-annotator --help
python -m pytest -q --maxfail=1
```

For GUI-marker tests (`-m gui`), install dev extras first so `pytest-qt` is available:

```bash
python -m pip install -e .[dev,cache]
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

See [Current Capabilities](docs/CURRENT_CAPABILITIES.md) for detailed, versioned feature status.

## Production Validation Commands

```bash
.venv-phage/bin/python -m pytest -q
QT_QPA_PLATFORM=offscreen .venv-phage/bin/python -m pytest -m gui --run-gui
```

## Documentation

- [Documentation Index](docs/README.md)
- [Architecture](docs/ARCHITECTURE.md)
- [Feature Access Guide](docs/FEATURE_ACCESS_GUIDE.md)
- [Source Reference](docs/SOURCE_REFERENCE.md)
- [Source Quality Audit](docs/SOURCE_QUALITY_AUDIT.md)
- [Assist Guide](docs/ASSIST_GUIDE.md)
- [Current Capabilities](docs/CURRENT_CAPABILITIES.md)
- [Planned Features](docs/PLANNED_FEATURES.md)
- [Fiji ThunderSTORM Bridge](docs/FIJI_THUNDERSTORM_BRIDGE.md)
- [SMLM Reproducibility Runbook](docs/SMLM_REPRODUCIBILITY_RUNBOOK.md)
- [Reports Index](docs/reports/README.md)

## Notes

- Fiji bridge mode executes JAR plugins through Fiji/ImageJ; configure executable + macro in the SMLM panel.
- If a CLI entrypoint is not found, reinstall in the active environment: `python -m pip install -e .`
- For release hygiene, generated artifacts (`*.egg-info`) and large demo binaries are intentionally not tracked.
