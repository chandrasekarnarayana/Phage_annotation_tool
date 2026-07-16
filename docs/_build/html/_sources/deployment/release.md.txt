# Release Checklist

Before release, run the full validation suite and rebuild documentation.

## Validation

```bash
python -m compileall -q src scripts tests
python scripts/check_source_quality.py
python scripts/check_import_integrity.py
python scripts/check_core_no_qt.py
python scripts/check_package_layout.py
python scripts/check_root_cleanliness.py
python -m pytest -q
make -C docs html
```

## Documentation

Confirm that:

- the quickstart matches the current CLI;
- feature reference pages match the GUI;
- API pages build without import errors;
- deployment docs match `project/environment.yml` and `project/runtime.spec.yml`;
- release notes describe user-visible changes.

## Packaging

Generated build artifacts, demo binaries, cache files, and HTML output should
not be committed unless a release process explicitly requires them.
