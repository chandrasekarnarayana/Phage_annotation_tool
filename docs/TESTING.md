# Test Suite Standards

This document defines test-suite conventions for maintainers and reviewers.

## 1. Suite Layout

- `tests/unit/`: deterministic unit tests (no network, no filesystem side effects outside temp dirs).
- `tests/integration/`: multi-module integration tests.
- `tests/integration/gui/`: Qt GUI integration tests.
- `tests/performance/`: benchmark/performance characterization tests.

Legacy root-level files under `tests/` should be migrated to one of the folders above as they are touched.

## 2. GUI Test Separation

- GUI tests are selected by `@pytest.mark.gui` (auto-applied by `tests/conftest.py` for Qt-dependent modules).
- GUI tests are excluded from default/core runs unless explicitly enabled.
- Core run command:
  - `python -m pytest -m "not gui"`
- GUI run command:
  - `python -m pytest -m gui --run-gui`

## 3. Naming Conventions

- File names: `test_<component>_<behavior>.py`
- Test class names: `Test<ComponentOrFeature>`
- Test function names: `test_<action>_<expected_result>`
- Prefer explicit behavior names over generic names (for example, `test_set_zoom_clamps_bounds` instead of `test_zoom`).

## 4. Test Ordering Inside Files

Keep tests in this order for readability:

1. Happy-path behavior
2. Edge/boundary conditions
3. Invalid input/error handling
4. Regression cases

Use section headers only when a file has multiple conceptual groups.

## 5. Style (PEP 8 + Documentation)

- Follow PEP 8 formatting and import ordering.
- Include a short module docstring describing scope.
- Use concise test docstrings that state behavior and expectation.
- Add comments only when intent is non-obvious; avoid narration comments.

## 6. Coverage Workflow

- Core CI collects coverage with:
  - `--cov=src/phage_annotator --cov-branch`
  - XML output at `artifacts/coverage-core.xml`
- Use coverage deltas to prioritize tests for low-coverage, high-risk modules (project/session I/O, async jobs, cache edge paths).
