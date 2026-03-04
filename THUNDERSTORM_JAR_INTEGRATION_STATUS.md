# ThunderSTORM JAR Integration Status

Last updated: March 4, 2026

## Current State (Verified)

ThunderSTORM bridge integration is implemented and operationally hardened in the codebase:

- Bundled macro exists: `external_plugins/thunderstorm_macro.ijm`
- Strict manifest exists: `external_plugins/Thunder_STORM.json`
- Optional second profile exists but is hidden from UI: `external_plugins/Thunder_STORM_FAST.json` (`ui_visible: false`)
- JAR discovery + `plugins.config` parsing is implemented
- Backends implemented:
  - `internal`
  - `fiji_subprocess`
  - `fiji_pyimagej`
- Preflight supports active probe mode (`--probe`) and deterministic exit codes
- Typed bridge errors are implemented (`FijiNotFoundError`, `MacroExecutionError`, `FijiTimeoutError`, `CSVSchemaMismatchError`, ...)
- UI includes execution plan/debug report + guided fix-it actions
- Optional CI lane for Fiji integration is present (`test-fiji-integration` job)

## What Is Not Guaranteed Yet

These are real remaining constraints (not framework-missing issues):

1. Real end-to-end Fiji execution still depends on local/runtime availability:
   - valid Fiji executable/app
   - compatible Java runtime
   - plugin command behavior on that environment

1. `fiji_pyimagej` is implemented but still environment-sensitive in practice.
   - It needs site-specific verification where it will be used.

1. Parity confidence is baseline-level, not exhaustive.
   - Existing parity tooling/tests are present, but fixture breadth can still be expanded.

## Operational Sign-Off Checklist

Use these commands before production use on a target machine:

```bash
python -m pip install -e . --no-build-isolation
python -m phage_annotator.smlm.preflight_cli --backend fiji_subprocess --plugin-id thunder_storm --fiji-exe /path/to/ImageJ-linux64 --probe
python -m phage_annotator.smlm.demo_cli --backend fiji_subprocess --plugin-id thunder_storm --fiji-exe /path/to/ImageJ-linux64 --probe-first --out-dir artifacts/smlm_demo
pytest -q tests/integration/test_fiji_thunderstorm.py -m integration
```

## Notes

- UI currently shows one ThunderSTORM plugin entry by default (`thunder_storm`).
- Additional profiles can exist for tooling/parity tests without being exposed in the GUI.
