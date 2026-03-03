# Fiji Plugin Manifest SDK

Last updated: March 2, 2026

## Goal

Enable repeatable integration of any Fiji plugin via:

- JAR in `external_plugins/`
- one strict JSON manifest
- no new Python glue per plugin

## Manifest Structure

Top-level:

- `plugin_id`
- `name`
- `jar_path`
- `macro_path` (optional)
- `plugin` (strict execution contract)

`plugin.identity`:

- `id`
- `display_name`
- `menu_path`
- `implementation_type`: `legacy_plugin | plugin_filter | extended_filter | scijava_command`

`plugin.invocation`:

- `run_command` (required)
- `arg_builder`: `ij_kv | json | template`
- `arg_template` (required only for `template`)
- `macro_template` (optional override)

`plugin.parameters` (typed schema):

- `name`
- `type`: `int | float | bool | choice | string`
- `default`
- `min` / `max` (numeric)
- `choices` (for `choice`)
- `required`
- `mutually_exclusive_with`

`plugin.io_contract`:

- `active_image_required`
- `roi_optional`
- `stack_required`
- `outputs`:
  - `updates_image`
  - `creates_overlay`
  - `writes_results_table`
  - `adds_rois`
  - `exports_files`

`plugin.execution_mode`:

- `ui_dialog`: `none | native | scripted`
- `threading`: `ui_thread | worker_thread`

## Runtime Behavior

If `macro_path` is missing and manifest is present:

1. Build typed/validated arg string from parameters.
2. Generate macro from manifest (`run_command` + arg builder/template).
3. Execute through selected backend (`fiji_subprocess` / `fiji_pyimagej`).
4. Capture executed macro text and plugin params in provenance metadata.

If `macro_path` exists, it is used directly (manifest still supplies metadata/env).

## Environment Variables Available to Macros

- `PHAGE_SMLM_INPUT`
- `PHAGE_SMLM_OUTPUT`
- `PHAGE_SMLM_PARAMS_JSON`
- `PHAGE_PLUGIN_ID`
- `PHAGE_PLUGIN_JAR`
- `PHAGE_PLUGIN_NAME`
- Backward compatibility:
  - `PHAGE_THUNDERSTORM_JAR`

## Minimal Onboarding Steps for New Plugin

1. Drop JAR into `external_plugins/`.
2. Add `<plugin>.json` manifest following this SDK.
3. Select plugin in SMLM panel, run `Preflight`, then run via Fiji backend.

## Auto-Metadata Enrichment

At discovery time, plugin JARs are scanned for `plugins.config` when present.
Detected menu entries and command names are attached to plugin descriptors and surfaced in UI diagnostics.

## Adapter Lifecycle Contract

This repository treats Fiji integration as a strict lifecycle:

1. `discover`: JAR discovery + `plugins.config` command extraction.
2. `describe`: strict manifest schema load/validation.
3. `materialize`: typed parameter coercion and macro template generation.
4. `execute`: backend dispatch (`fiji_subprocess` / `fiji_pyimagej`).
5. `validate`: output CSV schema checks against manifest expectations.
6. `observe`: preflight probe + demo runner + CI integration lane.
7. `recover`: UI debug report and fallback actions.

Contributors should not bypass this contract with ad-hoc plugin-specific code paths.
