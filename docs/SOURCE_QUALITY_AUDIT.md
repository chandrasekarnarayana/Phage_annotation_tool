# Source Quality Audit

This audit records the current modularity and documentation state of
`src/phage_annotator`.

## Summary

- Module docstrings: passing for all Python source files.
- Package organization: feature-oriented packages are present and enforced by
  `scripts/check_package_layout.py`.
- Root cleanliness: enforced by `scripts/check_root_cleanliness.py`.
- Qt boundary: headless/core package boundaries are enforced by
  `scripts/check_core_no_qt.py`.
- 300-line soft limit: improved, but not yet fully met outside the framework package.
- Function-level docstrings/comments: passing for all Python files in `src`, `scripts`, and `tests`.

Current source-only metrics:

- Source files: 316
- Source files over 300 lines: 75
- Module docstrings: passing for all Python source files.
- Functions/methods missing docstrings: 0.

## Largest Modularity Targets

These files should be split first because they combine many GUI actions,
rendering responsibilities, or session workflows:

| File | Lines | Suggested split direction |
| --- | ---: | --- |
| `src/phage_annotator/ui_qt/utils/ui_extra.py` | 3,583 | Split layout presets, command palette, logs, and helper dialogs. |
| `src/phage_annotator/ui_qt/actions/standard.py` | 3,044 | Split menu/action groups by File, View, Assist, QC, Layout, and Tools. |
| `src/phage_annotator/ui_qt/utils/ui_docks.py` | 2,099 | Split dock construction, dock state persistence, and panel routing. |
| `src/phage_annotator/ui_qt/controls/display.py` | 1,967 | Split contrast, modality display, projection, and synchronization controls. |
| `src/phage_annotator/ui_qt/controls/smlm.py` | 1,411 | Split backend setup, preflight, run controls, and result handling. |
| `src/phage_annotator/ui_qt/utils/export.py` | 1,324 | Split project save/load, annotation export, image export, and workspace state. |
| `src/phage_annotator/ui_qt/utils/ui_setup.py` | 1,295 | Split toolbar, panels, menus, canvas, and status setup. |
| `src/phage_annotator/session/controller_suggestions.py` | 1,259 | Split generation, review decisions, calibration, and ranking context. |
| `src/phage_annotator/analysis/suggestion_model.py` | 1,165 | Split candidate extraction, scoring, consensus, and model adaptation. |
| `src/phage_annotator/ui_qt/rendering/renderer.py` | 1,075 | Split frame preparation, render dispatch, overlays, and cache integration. |

## Documentation Standard

Use module docstrings for file purpose, class docstrings for domain role, and
function docstrings for behavior and flow. Prefer docstrings over low-value
inline comments. Add inline comments only around complex transforms, threading,
cache eviction, coordinate conversions, or GUI event-ordering logic.

`scripts/check_source_quality.py` enforces module docstrings and reports:

- files over the 300-line soft limit,
- functions/methods missing docstrings.

Function-docstring coverage currently passes across Python files. New or touched
functions should receive meaningful docstrings as part of the change.

## Recommended Cleanup Order

1. Split the largest Qt utility/action files into feature-named modules.
2. Move repeated GUI state logic into small services or session helpers.
3. Keep headless packages free of Qt imports.
4. Regenerate `docs/SOURCE_REFERENCE.md` after each docstring pass:

```bash
python scripts/generate_source_reference.py
```
