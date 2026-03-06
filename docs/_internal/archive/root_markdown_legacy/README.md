# Root Markdown Legacy Archive

This folder stores historical root-level Markdown files that were consolidated
into canonical docs under `docs/` and `docs/reports/`.

## Why archived

- They were transient status notes, milestone summaries, or overlapping
  topic documents.
- Keeping them at repository root created drift and duplicated sources of truth.

## Canonical replacements

- Runtime capabilities: `docs/CURRENT_CAPABILITIES.md`
- Active backlog + completed cleanup: `docs/PLANNED_FEATURES.md`
- Test and validation reports: `docs/reports/`
- Fiji bridge + SDK docs: `docs/FIJI_THUNDERSTORM_BRIDGE.md` and
  `docs/FIJI_PLUGIN_MANIFEST_SDK.md`

Do not add new root-level Markdown files for project docs. Keep authored docs
under `docs/` and index them in `docs/README.md`.
