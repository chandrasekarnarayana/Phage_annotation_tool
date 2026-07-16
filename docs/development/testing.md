# Testing

Testing covers import integrity, architecture boundaries, GUI behavior, session
commands, IO, cache behavior, SMLM bridge logic, QC validators, and performance
guards.

## Fast validation

```bash
python -m compileall -q src scripts tests
python scripts/check_source_quality.py
python scripts/check_import_integrity.py
python scripts/check_core_no_qt.py
python scripts/check_package_layout.py
python scripts/check_root_cleanliness.py
python -m pytest -q --maxfail=20
```

## GUI tests

GUI tests are marked with `gui`. They may require a display server or an
offscreen Qt platform:

```bash
QT_QPA_PLATFORM=offscreen python -m pytest -m gui --run-gui
```

## Architecture tests

Architecture tests are not style checks. They enforce dependency direction and
state ownership. When a refactor creates a new module that intentionally owns
state, update the guardrail allowlist and explain the ownership through the
module name and docstring.

## Performance and memory

Performance tests focus on avoiding unnecessary full-array allocation, keeping
cache budgets bounded, and preserving UI responsiveness under large images.
