"""Unit tests for SMLM bridge/parity/reproducibility helpers."""

from __future__ import annotations

import json
from pathlib import Path

from phage_annotator.algorithms.smlm_thunderstorm import Localization
from phage_annotator.smlm.backends import (
    ThunderstormBridgeConfig,
    _build_fiji_command,
    discover_bundled_thunderstorm_jar,
)
from phage_annotator.smlm.external_plugins import (
    build_manifest_macro,
    build_plugin_arg_string,
    discover_external_fiji_plugins,
    parse_plugins_config_from_jar,
    resolve_plugin_descriptor,
    resolve_plugin_jar,
    validate_plugin_parameters,
)
from phage_annotator.smlm.preflight import run_preflight
from phage_annotator.smlm.parity import compute_parity_metrics
from phage_annotator.smlm.reproducibility import (
    ReproducibilityRunbookState,
    append_provenance_event,
    export_reproducibility_bundle,
    lock_profile,
    resolve_profile,
)


def _loc(frame: int, x: float, y: float) -> Localization:
    return Localization(
        frame_index=frame,
        x_px=x,
        y_px=y,
        sigma_px=1.2,
        photons=120.0,
        background=10.0,
        uncertainty_px=0.2,
    )


def test_build_fiji_command_default() -> None:
    config = ThunderstormBridgeConfig(
        backend="fiji_subprocess",
        fiji_executable="/opt/Fiji/ImageJ-linux64",
        macro_path="/tmp/thunder.ijm",
    )
    cmd = _build_fiji_command(
        config=config,
        input_tif=Path("/tmp/in.tif"),
        output_csv=Path("/tmp/out.csv"),
        params_json=Path("/tmp/params.json"),
    )
    assert cmd[0] == "/opt/Fiji/ImageJ-linux64"
    assert "-macro" in cmd
    assert "/tmp/thunder.ijm" in cmd


def test_build_fiji_command_template() -> None:
    config = ThunderstormBridgeConfig(
        backend="fiji_subprocess",
        fiji_executable="/opt/Fiji/ImageJ-linux64",
        macro_path="/tmp/thunder.ijm",
        command_template="{fiji_executable} --headless --run {macro_path} input={input_tif} output={output_csv}",
    )
    cmd = _build_fiji_command(
        config=config,
        input_tif=Path("/tmp/in.tif"),
        output_csv=Path("/tmp/out.csv"),
        params_json=Path("/tmp/params.json"),
    )
    joined = " ".join(cmd)
    assert "--run /tmp/thunder.ijm" in joined
    assert "output=/tmp/out.csv" in joined


def test_parity_metrics_counts_and_error() -> None:
    internal = [_loc(0, 10.0, 10.0), _loc(0, 20.0, 20.0), _loc(1, 5.0, 5.0)]
    bridge = [_loc(0, 10.2, 10.1), _loc(0, 20.1, 20.0), _loc(1, 9.0, 9.0)]
    metrics = compute_parity_metrics(internal, bridge, tolerance_px=1.0)
    assert metrics.matched_count == 2
    assert metrics.precision == 2 / 3
    assert metrics.recall == 2 / 3
    assert metrics.mean_xy_error_px > 0


def test_runbook_lock_and_export(tmp_path: Path) -> None:
    state = ReproducibilityRunbookState(enabled=True)
    lock_profile(state, "ThunderSTORM", {"backend": "internal", "params": {"sigma_px": 1.3}})
    eff = resolve_profile(state, "ThunderSTORM", {"backend": "fiji_subprocess", "params": {"sigma_px": 2.0}})
    assert eff["backend"] == "internal"
    append_provenance_event(state, event_type="smlm_run_finished", payload={"detections": 12})

    out = export_reproducibility_bundle(
        state,
        out_path=tmp_path / "runbook.json",
        session_payload={"image_path": "/tmp/demo.tif"},
    )
    payload = json.loads(out.read_text(encoding="utf-8"))
    assert payload["runbook"]["enabled"] is True
    assert "ThunderSTORM" in payload["runbook"]["locked_profiles"]
    assert payload["runbook"]["provenance_events"][0]["event_type"] == "smlm_run_finished"
    assert isinstance(payload.get("sha256"), str)


def test_discover_bundled_thunderstorm_jar(tmp_path: Path) -> None:
    plugin_dir = tmp_path / "external_plugins"
    plugin_dir.mkdir()
    jar = plugin_dir / "Thunder_STORM.jar"
    jar.write_bytes(b"jar")
    discovered = discover_bundled_thunderstorm_jar(tmp_path)
    assert discovered == jar.resolve()


def test_discover_external_plugins_manifest_and_jar(tmp_path: Path) -> None:
    plugin_dir = tmp_path / "external_plugins"
    plugin_dir.mkdir()
    jar = plugin_dir / "FancyPlugin.jar"
    jar.write_bytes(b"jar")
    manifest = plugin_dir / "fancy.json"
    manifest.write_text(
        json.dumps(
            {
                "plugin_id": "fancy_plugin",
                "name": "Fancy Plugin",
                "jar_path": "FancyPlugin.jar",
                "env": {"FIJI_FANCY_MODE": "1"},
            }
        ),
        encoding="utf-8",
    )
    discovered = discover_external_fiji_plugins(tmp_path)
    assert len(discovered) == 1
    assert discovered[0].plugin_id == "fancy_plugin"
    assert discovered[0].jar_path.endswith("FancyPlugin.jar")
    assert resolve_plugin_jar("fancy_plugin", "", start_dir=tmp_path).endswith("FancyPlugin.jar")
    desc = resolve_plugin_descriptor("fancy_plugin", start_dir=tmp_path)
    assert desc is not None
    assert desc.env.get("FIJI_FANCY_MODE") == "1"


def test_strict_manifest_arg_and_macro(tmp_path: Path) -> None:
    plugin_dir = tmp_path / "external_plugins"
    plugin_dir.mkdir()
    jar = plugin_dir / "AnyPlugin.jar"
    jar.write_bytes(b"jar")
    manifest = plugin_dir / "any.plugin.json"
    manifest.write_text(
        json.dumps(
            {
                "plugin_id": "any_plugin",
                "name": "Any Plugin",
                "jar_path": "AnyPlugin.jar",
                "plugin": {
                    "jar_path": "AnyPlugin.jar",
                    "identity": {
                        "id": "any_plugin",
                        "display_name": "Any Plugin",
                        "menu_path": "Plugins>Any",
                        "implementation_type": "legacy_plugin",
                    },
                    "invocation": {
                        "run_command": "Any Plugin Command",
                        "arg_builder": "ij_kv",
                    },
                    "parameters": [
                        {"name": "threshold", "type": "float", "default": 1.5, "min": 0.1, "max": 10.0},
                        {"name": "mode", "type": "choice", "default": "fast", "choices": ["fast", "accurate"]},
                    ],
                    "io_contract": {"outputs": {"writes_results_table": True}},
                    "schema": {
                        "plugin_version_tested": "1.0.0",
                        "csv_schema_version": "ts-v1",
                        "required_columns": ["x [px]", "y [px]"],
                        "optional_columns": ["sigma [px]"],
                        "separator": ",",
                        "decimal": "."
                    },
                    "execution_mode": {"ui_dialog": "none", "threading": "worker_thread"},
                },
            }
        ),
        encoding="utf-8",
    )
    plugin = discover_external_fiji_plugins(tmp_path)[0]
    assert plugin.manifest is not None
    assert plugin.manifest.plugin_version_tested == "1.0.0"
    assert plugin.manifest.csv_schema_version == "ts-v1"
    assert "x [px]" in plugin.manifest.required_columns
    values = validate_plugin_parameters(plugin.manifest, {"threshold": 2.5, "mode": "accurate"})
    assert values["threshold"] == 2.5
    args = build_plugin_arg_string(plugin, values)
    assert "threshold=2.5" in args
    assert "mode=accurate" in args
    macro = build_manifest_macro(plugin, args)
    assert 'run("Any Plugin Command"' in macro


def test_parse_plugins_config_from_jar(tmp_path: Path) -> None:
    import zipfile

    jar = tmp_path / "test.jar"
    with zipfile.ZipFile(jar, "w") as zf:
        zf.writestr(
            "plugins.config",
            'Plugins>Test, "My Command", com.example.Plugin\n',
        )
    menus, commands = parse_plugins_config_from_jar(str(jar))
    assert menus == ["Plugins>Test"]
    assert commands == ["My Command"]


def test_preflight_internal_backend_passes() -> None:
    report = run_preflight(ThunderstormBridgeConfig(backend="internal"))
    assert report.ok is True


def test_preflight_probe_missing_fiji_returns_code_2() -> None:
    report = run_preflight(
        ThunderstormBridgeConfig(
            backend="fiji_subprocess",
            fiji_executable="",
            plugin_id="thunder_storm",
        ),
        probe=True,
    )
    assert report.ok is False
    assert report.exit_code == 2


def test_second_plugin_profile_discovered_from_repository_assets() -> None:
    discovered = discover_external_fiji_plugins()
    ids = {p.plugin_id for p in discovered}
    assert "thunder_storm" in ids
    assert "thunder_storm_fast" in ids
