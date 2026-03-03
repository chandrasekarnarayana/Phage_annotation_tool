"""CLI utilities for external Fiji plugin manifest onboarding."""

from __future__ import annotations

import json
from pathlib import Path

import click

from phage_annotator.smlm.external_plugins import (
    discover_external_fiji_plugins,
    parse_plugins_config_from_jar,
)


@click.group(context_settings={"help_option_names": ["-h", "--help"]})
def main() -> None:
    """Fiji plugin adapter tooling."""


@main.command("list-commands")
@click.option("--jar", "jar_path", type=click.Path(path_type=Path), required=True)
def list_commands(jar_path: Path) -> None:
    """List commands discovered from plugins.config inside a jar."""
    menus, commands = parse_plugins_config_from_jar(str(jar_path))
    if not commands:
        click.echo("No commands discovered.")
        raise SystemExit(3)
    click.echo("Commands:")
    for i, cmd in enumerate(commands, 1):
        menu = menus[i - 1] if i - 1 < len(menus) else "(menu unknown)"
        click.echo(f"{i:2d}. {cmd} [{menu}]")


@main.command("validate-manifest")
@click.option("--manifest", type=click.Path(path_type=Path), required=True)
def validate_manifest(manifest: Path) -> None:
    """Validate strict manifest by discovery parsing."""
    if not manifest.exists():
        click.echo(f"Manifest not found: {manifest}")
        raise SystemExit(2)
    if manifest.parent.name == "external_plugins":
        plugin_dir = manifest.parent.parent
    else:
        plugin_dir = manifest.parent
    try:
        discovered = discover_external_fiji_plugins(plugin_dir)
    except Exception as exc:
        click.echo(f"Manifest validation failed: {exc}")
        raise SystemExit(2)
    target = manifest.resolve()
    for plugin in discovered:
        if plugin.manifest_path and Path(plugin.manifest_path).resolve() == target:
            click.echo(f"Manifest valid for plugin: {plugin.plugin_id} ({plugin.name})")
            if plugin.manifest is not None:
                click.echo(f"run_command: {plugin.manifest.run_command}")
            return
    click.echo("Manifest parsed but no plugin descriptor matched this file.")
    raise SystemExit(2)


@main.command("scaffold-manifest")
@click.option("--jar", "jar_path", type=click.Path(path_type=Path), required=True)
@click.option("--plugin-id", required=True, help="Plugin id slug, e.g. thunder_storm")
@click.option("--name", "display_name", required=True, help="Display name")
@click.option("--out", "out_path", type=click.Path(path_type=Path), required=True)
def scaffold_manifest(jar_path: Path, plugin_id: str, display_name: str, out_path: Path) -> None:
    """Generate a starter strict manifest JSON from jar command discovery."""
    menus, commands = parse_plugins_config_from_jar(str(jar_path))
    command = commands[0] if commands else display_name
    menu_path = menus[0] if menus else "Plugins"
    payload = {
        "plugin_id": plugin_id,
        "name": display_name,
        "jar_path": jar_path.name if jar_path.name else str(jar_path),
        "description": f"{display_name} plugin manifest scaffold",
        "plugin": {
            "jar_path": jar_path.name if jar_path.name else str(jar_path),
            "identity": {
                "id": plugin_id,
                "display_name": display_name,
                "menu_path": menu_path,
                "implementation_type": "legacy_plugin",
            },
            "invocation": {
                "run_command": command,
                "arg_builder": "ij_kv",
                "arg_template": "",
                "macro_template": (
                    "setBatchMode(true);\\n"
                    "run(\\\"${PHAGE_PLUGIN_COMMAND}\\\", \\\"${PHAGE_PLUGIN_ARG_STRING}\\\");\\n"
                    "if (\\\"${PHAGE_SMLM_OUTPUT}\\\" != \\\"\\\") saveAs(\\\"Results\\\", \\\"${PHAGE_SMLM_OUTPUT}\\\");\\n"
                ),
            },
            "parameters": [],
            "io_contract": {
                "active_image_required": True,
                "roi_optional": True,
                "stack_required": False,
                "outputs": {
                    "updates_image": False,
                    "creates_overlay": False,
                    "writes_results_table": True,
                    "adds_rois": False,
                    "exports_files": True,
                },
            },
            "schema": {
                "plugin_version_tested": "",
                "csv_schema_version": "",
                "required_columns": ["x [px]", "y [px]"],
                "optional_columns": [],
                "separator": ",",
                "decimal": ".",
            },
            "execution_mode": {"ui_dialog": "none", "threading": "worker_thread"},
        },
    }
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    click.echo(f"Scaffolded manifest: {out_path}")


if __name__ == "__main__":
    main()
