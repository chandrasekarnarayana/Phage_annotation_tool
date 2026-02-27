# Testing Strategy and Quality Plan

## Document Control

| Field | Value |
|---|---|
| Project | Phage Annotation Tool |
| Version | 0.1 |
| Date | 2026-02-27 |
| Audience | Developers, software reviewers, JOSS reviewers |
| Scope | Test organization, coverage posture, missing-test plan, CI strategy |

## 1. Current State Snapshot

### 1.1 Test Slice Separation

- Core slice collection command: `python -m pytest -m "not gui" --collect-only -q`
  - Collected tests: **545**
- GUI slice collection command: `python -m pytest -m gui --run-gui --collect-only -q`
  - Collected tests: **310**

### 1.2 Core Execution Baseline

- Command:
  - `python -m pytest -m "not gui" --cov=src/phage_annotator --cov-branch --cov-report=term-missing:skip-covered`
- Result:
  - **527 passed**
  - **18 skipped**
  - **0 failed**
- Runtime: ~13.5s (local execution in this environment)

### 1.3 Coverage Baseline (Core Run)

- Total reported coverage: **17.93%**
- Note: this is diluted by many non-executed GUI-heavy modules and optional subsystem paths included in `src/phage_annotator`.
- Immediate interpretation: useful for identifying gaps, not yet a suitable single KPI for release gating.

## 2. Test Architecture Policy

### 2.1 Directory Contract

- `tests/unit/`: pure logic and deterministic component behavior.
- `tests/integration/`: cross-module interactions and I/O integration.
- `tests/integration/gui/`: Qt wiring and end-to-end UI behavior.
- `tests/performance/`: benchmark or throughput/latency characterization.

### 2.2 GUI Isolation Contract

- GUI tests are opt-in with `--run-gui`.
- GUI tests are marked `gui` (including auto-marking in `tests/conftest.py` for Qt-dependent modules).
- GUI tests are excluded from core collection by default.
- CI runs core and GUI slices in separate jobs.

### 2.3 Collection Safety

- `tests/conftest.py` now:
  - normalizes path handling across pytest versions;
  - auto-detects Qt-dependent test modules;
  - auto-marks those modules as `gui`;
  - prevents GUI module collection in core runs (avoids import-time Qt crashes);
  - avoids false positives from `-m "not gui"` marker expressions.

## 3. Naming, Ordering, and Style Standards

See `tests/README.md` for contributor-level rules. Key enforced conventions:

- Files: `test_<component>_<behavior>.py`
- Tests: `test_<action>_<expected_result>`
- In-file ordering:
  1. happy path,
  2. edge/boundary,
  3. invalid/error,
  4. regression.
- Style: PEP 8, concise docstrings, comments only where intent is non-obvious.

## 4. Coverage Gaps and Missing Tests

Priority was assigned by risk (state persistence, I/O integrity, async behavior, and user-visible runtime failures).

### P0 (High Risk, Low Coverage)

1. `src/phage_annotator/session/project.py`
- Risk: project persistence correctness and backward compatibility.
- Add tests for full roundtrip with mixed modalities, missing files, and migration payloads.

2. `src/phage_annotator/session/annotation_io.py`
- Risk: data-loss or schema drift in import/export.
- Add property-based roundtrip tests and malformed payload handling.

3. `src/phage_annotator/io/metadata/*`
- Risk: fragile metadata parsing across real-world microscopy files.
- Add fixture-driven parser tests for incomplete and inconsistent metadata records.

### P1 (Medium-High Risk)

1. `src/phage_annotator/session/images.py`, `session/view.py`, `session/controller.py`
- Add behavioral tests for state transitions and invalid view operations.

2. `src/phage_annotator/cache/projection_cache.py`
- Add tests for modality byte-accounting and eviction edge cases across mixed key sets.

3. `src/phage_annotator/framework/plugin.py`
- Add plugin discovery, error-isolation, and registration lifecycle tests.

### P2 (Performance and Optional Paths)

1. `src/phage_annotator/algorithms/density_*` and `deepstorm_*`
- Add tests for optional dependency absence and fallback behavior.

2. `src/phage_annotator/rendering/mpl.py`
- Add non-GUI rendering correctness tests with deterministic image fixtures.

## 5. CI and Governance Plan

### 5.1 Current CI Improvements Applied

- Core job now emits:
  - JUnit XML
  - core pytest log
  - coverage XML (`artifacts/coverage-core.xml`)
- Core artifacts upload changed to `if: always()` for post-run diagnostics.

### 5.2 Proposed Ratcheting Policy

Use staged quality gates instead of immediate hard thresholds:

1. Stage A (now)
- Collect and publish coverage; no strict fail-under gate.

2. Stage B
- Introduce component-level threshold on selected packages:
  - `session/*`, `io/projects/*`, `cache/*`.

3. Stage C
- Add global fail-under once major zero-coverage surfaces are addressed.

## 6. Organization Debt and Refactor Plan

Root-level `tests/test_*.py` files have been migrated to canonical locations:

- `tests/unit/annotation/test_multi_modality_annotations.py`
- `tests/unit/session/test_projection_ui_logic.py`
- `tests/integration/gui/test_projection_ui_wiring.py`
- `tests/unit/ui_qt/test_sidebar_manager.py`
- `tests/integration/test_sync_propagation_integration.py`
- `tests/unit/data/test_sync_rules.py`

Ongoing policy:

- Keep new tests in `unit/`, `integration/`, or `integration/gui/` only.
- Enforce via CI guard to prevent future root-level drift.

## 7. Immediate Next Actions (Recommended)

1. Add P0 tests for `session/project.py` and `session/annotation_io.py`.
2. Add a coverage summary section in release/report docs for each milestone.
3. Add per-package coverage ratcheting for `session/*`, `io/projects/*`, and `cache/*`.
