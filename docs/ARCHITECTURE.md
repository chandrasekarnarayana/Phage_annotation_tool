# Architecture

This project uses a `src/` package layout with explicit boundaries between
headless domain code, IO, session orchestration, and Qt presentation code.

## Package Boundaries

- `phage_annotator.algorithms`: numerical algorithms and image-processing functions.
- `phage_annotator.analysis`: suggestion, QC, learning, and analytics logic.
- `phage_annotator.annotation`: annotation schemas, metadata, taxonomy, and persistence helpers.
- `phage_annotator.cache`: reusable cache implementations and memory-aware cache policies.
- `phage_annotator.config` and `phage_annotator.constants`: runtime configuration and stable defaults.
- `phage_annotator.core`: headless domain types and state snapshots.
- `phage_annotator.data`: dataset abstractions, pyramids, display mapping, and source adapters.
- `phage_annotator.framework`: command, event, job, plugin, and service primitives.
- `phage_annotator.io`: file readers, project persistence, metadata readers, and standard exports.
- `phage_annotator.rendering`: backend-independent rendering helpers.
- `phage_annotator.roi`: ROI commands, managers, interactors, and widgets.
- `phage_annotator.session`: application session state, commands, navigation, persistence, and sync.
- `phage_annotator.smlm`, `density`, and `deepstorm`: specialized analysis backends and entrypoints.
- `phage_annotator.ui_qt`: Qt-only windows, panels, controls, actions, services, and widgets.
- `phage_annotator.runtime`: startup environment checks and operational policy.
- `phage_annotator.tools` and `scripts`: developer and CI tooling.

Headless packages must not import Qt. The CI guard `scripts/check_core_no_qt.py`
keeps that boundary explicit.

## Source Quality Rules

Every Python file must have a module docstring. File names should describe the
file's responsibility rather than an implementation accident.

Files should stay below a 300-line soft limit. When a file grows beyond that
limit, prefer extracting cohesive helpers into a sibling module named after the
new responsibility. Existing oversized modules are reported by
`scripts/check_source_quality.py` so refactoring pressure remains visible without
forcing risky broad rewrites in unrelated changes.

## Testing Strategy

- `tests/unit`: fast tests for isolated behavior and package contracts.
- `tests/integration`: workflow tests that cross package boundaries.
- `tests/integration/gui`: Qt wiring and GUI state tests.
- `tests/performance`: benchmark and performance-regression checks.

CI runs import integrity, package layout, source quality, Qt boundary, acyclic
import, release hygiene, Markdown quality, core tests, GUI tests, and benchmark
gates.

## Memory And Responsiveness

Startup runs `project/environment.yml` validation before the GUI is created. Runtime
policy is centralized in `phage_annotator.runtime.operational_policy`, which
bounds the global cache budget and background worker count. Defaults preserve UI
responsiveness by capping workers and deriving cache memory from available RAM.
The CLI applies this policy when creating the application context, so cache and
thread-service limits are established before any GUI work begins.

Operators can tune these without editing code:

```bash
PHAGE_ANNOTATOR_MAX_WORKERS=2 PHAGE_ANNOTATOR_CACHE_MB=2048 phage-annotator
```

## Deployment

The package is built with setuptools from `pyproject.toml`. Console entrypoints
are declared under `[project.scripts]`, and releases publish to PyPI through
`.github/workflows/publish.yml` when a GitHub release is published.

Recommended release sequence:

```bash
python scripts/check_source_quality.py
python scripts/check_package_layout.py
python scripts/check_release_hygiene.py
python -m pytest -q
python -m build
python -m twine check dist/*
```
