# Fiji/ThunderSTORM Bridge

Last updated: March 2, 2026

## Summary

Phage Annotator now supports a selectable ThunderSTORM backend:

- `internal` (native Python pipeline)
- `fiji_subprocess` (headless Fiji/ImageJ process)
- `fiji_pyimagej` (PyImageJ headless execution)

This enables use of Fiji JAR plugins from the Python toolchain without rewriting plugin code.

## Preflight

Use preflight before first run:

- UI: `SMLM -> ThunderSTORM -> Preflight`
- CLI: `phage-annotator-smlm-preflight --backend fiji_subprocess --fiji-exe <path>`
- Active probe: `phage-annotator-smlm-preflight --probe --backend fiji_subprocess --fiji-exe <path>`
- Demo run: `phage-annotator-smlm-run-demo --backend fiji_subprocess --plugin-id thunder_storm --probe-first --fiji-exe <path>`

Preflight validates executable/runtime/plugin/macro/output prerequisites with actionable pass/fail messages.
`--probe` additionally launches Fiji headless, invokes plugin command, and verifies output marker creation.

Probe exit codes:

- `0`: OK
- `2`: Fiji not runnable
- `3`: plugin command not discoverable
- `4`: macro execution failed
- `5`: probe output marker missing

SMLM now shows a guided fix card on preflight/probe failure, with exit-code-specific actions:

- `2`: set Fiji paths and rerun probe
- `3`: select JAR, list commands, rerun probe
- `4`: inspect generated macro/logs and rerun probe
- `5`: inspect output/logs and rerun probe

## Multiple Plugin Integration

`external_plugins/` can host multiple Fiji JAR plugins.

- Place JARs directly (`*.jar`) for auto-discovery.
- Optionally add plugin manifests (`*.json`) to define:
  - `plugin_id`
  - `name`
  - `jar_path`
  - optional `macro_path`
  - optional `env` map

In the SMLM panel, the `Plugin` dropdown now selects discovered plugins and auto-fills the plugin JAR path.
The repository ships two plugin profiles (`thunder_storm`, `thunder_storm_fast`) to prove manifest-only onboarding using the same JAR with no backend glue changes.

For strict per-plugin invocation contracts, see
`docs/FIJI_PLUGIN_MANIFEST_SDK.md`.

ThunderSTORM manifest now includes schema guardrails:

- `plugin_version_tested`
- `csv_schema_version`
- `required_columns` / `optional_columns`
- CSV `separator` and `decimal` expectations

Manifest/command onboarding helpers:

- `phage-annotator-fiji-plugin-tool list-commands --jar <path/to/plugin.jar>`
- `phage-annotator-fiji-plugin-tool scaffold-manifest --jar <path> --plugin-id my_plugin --name "My Plugin" --out external_plugins/my_plugin.json`
- `phage-annotator-fiji-plugin-tool validate-manifest --manifest external_plugins/my_plugin.json`

Offline install note:

- `python -m pip install -e . --no-build-isolation`

## How JAR Plugins Work Here

- Fiji/ThunderSTORM remains Java-side (`.jar` plugins inside Fiji/ImageJ).
- Phage Annotator launches Fiji in headless mode (subprocess or PyImageJ).
- The bridge passes:
  - input stack path
  - output CSV path
  - parameter JSON path
- Your Fiji macro/script performs plugin execution and writes ThunderSTORM CSV output.
- Phage Annotator reads the CSV and maps it back into normalized localization objects/overlays.

## Required Inputs for Bridge Backends

Set in `SMLM -> ThunderSTORM` panel:

- `Backend`:
  - `fiji_subprocess` or `fiji_pyimagej`
- `Fiji executable` (subprocess backend)
- `Fiji macro/script` (both Fiji bridge backends)
- `ThunderSTORM JAR` (optional if your macro needs explicit plugin path)
- Optional `Fiji command template` (subprocess override)
- Optional `PyImageJ app path` (PyImageJ backend)

If `external_plugins/Thunder_STORM.jar` exists in the project root, it is auto-detected and prefilled.

## Macro Variable Contract

For reliable bridge execution, your macro/script should consume:

- `PHAGE_SMLM_INPUT`
- `PHAGE_SMLM_OUTPUT`
- `PHAGE_SMLM_PARAMS_JSON`
- `PHAGE_THUNDERSTORM_JAR` (when configured or auto-detected)
- `PHAGE_PLUGIN_ID`
- `PHAGE_PLUGIN_JAR`
- `PHAGE_PLUGIN_NAME` (when plugin metadata is available)

For PyImageJ mode, placeholder replacement is also supported in macro text:

- `${PHAGE_SMLM_INPUT}`
- `${PHAGE_SMLM_OUTPUT}`
- `${PHAGE_SMLM_PARAMS_JSON}`
- `${PHAGE_THUNDERSTORM_JAR}`
- `${PHAGE_PLUGIN_ID}`
- `${PHAGE_PLUGIN_JAR}`
- `${PHAGE_PLUGIN_NAME}`

## Notes

- Bridge mode is designed for parity and interoperability, not to replace Fiji.
- Optional runtime dependencies for PyImageJ mode are in `pip install .[fiji]`.
