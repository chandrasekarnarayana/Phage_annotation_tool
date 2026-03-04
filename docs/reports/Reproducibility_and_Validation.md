# Reproducibility and Validation

## Document Control
| Field | Value |
|---|---|
| Project | Phage Annotation Tool |
| Document Version | 0.2-draft |
| Report Date | 2026-02-27 |
| Companion Report | `docs/reports/Design_Report.md` |

## 1. Reproducibility Goals
- Provide exact setup and validation commands that can be replayed.
- Separate verified behavior from environment-blocked behavior.
- Capture enough environment metadata for reviewer-side comparison.

## 2. Environment Specification
Status: Complete

### 2.1 Required Runtime
| Component | Version/Constraint | Notes |
|---|---|---|
| Python | `>=3.9` (declared) | `pyproject.toml` requirement |
| Tested interpreter in this audit | `Python 3.12.9` | `/home/cs/miniconda3/bin/python` |
| OS (audit host) | Ubuntu Linux kernel `6.8.0-101-generic`, x86_64 | `uname -a` |
| Core dependencies | `numpy`, `pandas`, `matplotlib`, `click`, `pyqt5`, `tifffile`, `scipy`, `lmfit` | From `pyproject.toml` |
| Dev dependencies | `pytest`, `pytest-cov`, `pytest-qt`, `pytest-benchmark` | From `[project.optional-dependencies].dev` |

### 2.2 Optional/Conditional Dependencies
| Dependency | Needed For | Status in this audit |
|---|---|---|
| Qt bindings (`PyQt5` and backend components) | GUI runtime and many UI/session tests | Missing/incomplete (`PyQt5.sip` errors) |
| `pytest-benchmark` | Benchmark test execution | Missing (benchmark test skipped) |
| `psutil` | Memory pressure performance tests | Not validated in this audit |
| `scikit-image` | Enhanced threshold/particle paths | Optional; fallback logic exists |

## 3. Setup Procedure
Status: Complete

### 3.1 Clean Setup Commands
```bash
python -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
python -m pip install -e ".[dev,cache]"
```

### 3.2 Environment Verification
```bash
python --version
python -c "import sys; print(sys.executable)"
python -m pip --version
pytest --version
```

Optional Qt verification:
```bash
python -c "from PyQt5 import QtCore; print(QtCore.PYQT_VERSION_STR)"
```

## 4. Validation Execution
Status: Complete (bounded)

### 4.1 Commands Executed During Current Audit
```bash
pytest tests/unit/session/test_modality_system.py tests/unit/data/test_sync_rules.py tests/unit/annotation/test_multi_modality_annotations.py
pytest tests/unit/structure/test_structure_integrity.py
pytest tests/unit/session/test_session_components.py
pytest tests/unit/test_modality_persistence.py
pytest tests/unit/io/test_io_axes.py tests/unit/algorithms/test_projection.py tests/unit/cache/test_projection_cache_modality.py
python scripts/check_import_integrity.py
python scripts/check_core_no_qt.py
python scripts/check_package_layout.py
pytest --collect-only -q
pytest tests/performance/test_perf.py
```

### 4.2 Observed Results
- `92 passed` for modality/sync/multi-modality annotation subset.
- `4 passed` for structure integrity suite.
- `5 passed` for session component suite.
- `10 passed` for modality persistence suite.
- `18 passed` for io/projection/cache subset.
- Import/layout guard scripts passed.
- `pytest --collect-only -q` reported 13 collection errors (Qt-related imports).
- Performance smoke `tests/performance/test_perf.py`: `1 skipped` (missing `pytest-benchmark`).

### 4.3 Known Environment Blockers
| Command Scope | Error Signature | Root Cause | Resolution |
|---|---|---|---|
| Qt-dependent tests | `ModuleNotFoundError: No module named 'PyQt5.sip'` | Qt binding stack incomplete in runtime | Install compatible PyQt5 + backend packages |
| Qt-dependent tests | `ImportError: Failed to import ... Qt binding modules` | No usable Qt backend for matplotlib Qt compatibility | Install supported Qt binding and backend |
| Benchmark tests | `pytest.importorskip("pytest_benchmark")` -> skipped | Missing benchmark plugin | `python -m pip install pytest-benchmark` |

## 5. Full Validation Matrix
Status: Complete

| Validation Area | Command | Expected Output | Current Status |
|---|---|---|---|
| Modality core | `pytest tests/unit/session/test_modality_system.py` | Pass | Executed (pass) |
| Display sync rules | `pytest tests/unit/data/test_sync_rules.py` | Pass | Executed (pass) |
| Multi-modality annotation helpers | `pytest tests/unit/annotation/test_multi_modality_annotations.py` | Pass | Executed (pass) |
| Structure guards | `pytest tests/unit/structure/test_structure_integrity.py` | Pass | Executed (pass) |
| Session command helpers | `pytest tests/unit/session/test_session_components.py` | Pass | Executed (pass) |
| Modality persistence | `pytest tests/unit/test_modality_persistence.py` | Pass | Executed (pass) |
| IO/projection/cache core | `pytest tests/unit/io/test_io_axes.py tests/unit/algorithms/test_projection.py tests/unit/cache/test_projection_cache_modality.py` | Pass | Executed (pass) |
| Qt-dependent unit/integration | `pytest -m gui --run-gui` or equivalent suites | Pass | Blocked by Qt runtime |
| Benchmark suite | `pytest tests/performance -q` | Stable benchmark output | Partial/blocked (plugin/runtime gaps) |

## 6. Benchmark Reproduction Plan
Status: Partial

### 6.1 Benchmark Scenarios
| Scenario ID | Scenario | Metric | Target |
|---|---|---|---|
| BENCH-001 | Axis standardization (`standardize_axes`) | time per call | Establish baseline in Qt-capable dev env |
| BENCH-002 | Display mapping micro-ops | time/op and memory footprint | Establish baseline and drift threshold |
| BENCH-003 | Projection cache behavior under modality keys | hit ratio and eviction rate | Track against representative dataset workload |

### 6.2 Benchmark Commands
```bash
python -m pip install pytest-benchmark
pytest tests/performance/test_perf.py -q
pytest tests/unit/ui_qt/test_bcontrast_performance.py -q
```

### 6.3 Hardware and Runtime Capture (Current Audit Host)
- CPU: AMD Ryzen 7 5800H (16 logical CPUs)
- RAM: 13 GiB total (observed high pressure during audit)
- OS: Linux x86_64, kernel `6.8.0-101-generic`
- Python: `3.12.9`

## 7. Dataset and Artifact Provenance
Status: Partial

### 7.1 Input Data Catalog
| Dataset ID | Source | License | Checksum | Notes |
|---|---|---|---|---|
| DS-001 | Generated by `phage-annotator` (no args) | Project-controlled generated artifact | n/a | Writes `phage_annotator_demo.tif` |
| DS-002 | User-provided TIFF/OME-TIFF | User/environment dependent | n/a | Not redistributed by this report |

### 7.2 Output Artifact Policy
- Test evidence is captured as command output and report text in this folder.
- Project files are serialized as `.phageproj` plus per-image `.annotations.json`.
- Recovery snapshots are stored under `<project_dir>/.recovery/`.

## 8. Determinism and Variability
Status: Partial

### 8.1 Determinism Controls
- Serialization and axis-standardization logic are deterministic for fixed inputs.
- For benchmark reproducibility, set explicit seeds in random-data tests and pin dependency versions.

### 8.2 Acceptable Variability
- Runtime-dependent performance can vary with CPU load, memory pressure, and backend availability.
- Until baseline thresholds are defined, performance comparisons should be qualitative only.

## 9. Reviewer Checklist
Status: Complete

| Item | Yes/No | Evidence |
|---|---|---|
| Environment setup documented | Yes | Sections 2-3 |
| Commands are copy-paste reproducible | Yes | Section 4.1 |
| Validation scope explicit | Yes | Sections 4-5 |
| Blockers and limitations explicit | Yes | Section 4.3 |
| Evidence artifacts linked | Partial | Command outputs summarized; no attached raw logs bundle |

## 10. Release-Grade Reproducibility Sign-off
Status: Pending

### 10.1 Pre-Release Gate
- All core tests pass in a clean environment.
- Qt-dependent tests pass in a Qt-capable environment.
- Benchmark suite executes with `pytest-benchmark` and produces baseline report.
- Known limitations and licensing/citation publication constraints are documented.

### 10.2 Sign-off Table
| Role | Name | Date | Decision |
|---|---|---|---|
| Technical Lead | [Fill] | [Fill] | [Approve/Block] |
| QA/Validation Reviewer | [Fill] | [Fill] | [Approve/Block] |
| Release Manager | [Fill] | [Fill] | [Approve/Block] |
