# CI Notes

This document describes how to reproduce CI locally and how to interpret common failures.

## Local Reproduction
- Core tests (no GUI): `python -m pytest -m "not gui" --ignore=tests/test_gui_basic.py`
- GUI tests (requires Qt + display or offscreen): `python -m pytest -m gui --run-gui`
- Lint: `ruff check src tests`
- Mypy (core only): `mypy --ignore-missing-imports --follow-imports=skip src/phage_annotator/io.py src/phage_annotator/analysis.py src/phage_annotator/annotations.py src/phage_annotator/project_io.py src/phage_annotator/projection_cache.py src/phage_annotator/pyramid.py src/phage_annotator/ring_buffer.py`
- Core Qt import guard: `python scripts/check_core_no_qt.py`

## GUI/Headless Tips
- Linux headless: `QT_QPA_PLATFORM=offscreen MPLBACKEND=Agg xvfb-run -a python -m pytest -m gui --run-gui`
- macOS/Windows headless: `QT_QPA_PLATFORM=offscreen MPLBACKEND=Agg python -m pytest -m gui --run-gui`

## Common Failure Modes and Fixes
- Qt platform plugin errors:
  - Ensure `QT_QPA_PLATFORM=offscreen` and `MPLBACKEND=Agg` are set.
  - Linux: run under `xvfb-run`.
- GUI import failures during collection:
  - Ensure GUI imports are inside test functions and guarded with `pytest.importorskip("PyQt5")`.
  - Mark GUI tests with `@pytest.mark.gui` and run with `--run-gui`.
- Missing `create_app`:
  - Use `phage_annotator.gui_mpl.create_app` (shim provided).
- Windows path issues:
  - Use `pathlib.Path` and `tmp_path` fixtures in tests.
- Long-running GUI tests:
  - Keep GUI tests minimal; do not load large stacks in CI.

## Artifacts
On CI failure, artifacts contain:
- `artifacts/pytest-*.log`: pytest log output
- `artifacts/junit-*.xml`: JUnit test results
