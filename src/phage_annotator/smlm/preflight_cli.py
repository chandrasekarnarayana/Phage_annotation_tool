"""CLI entry point for SMLM/Fiji bridge preflight."""

from __future__ import annotations

from pathlib import Path

import click

from phage_annotator.smlm.backends import ThunderstormBridgeConfig
from phage_annotator.smlm.preflight import report_to_text, run_preflight


@click.command(context_settings={"help_option_names": ["-h", "--help"]})
@click.option("--backend", type=click.Choice(["internal", "fiji_subprocess", "fiji_pyimagej"]), default="internal")
@click.option("--fiji-exe", type=click.Path(path_type=Path), default=None)
@click.option("--fiji-macro", type=click.Path(path_type=Path), default=None)
@click.option("--plugin-id", type=str, default="thunder_storm")
@click.option("--plugin-jar", type=click.Path(path_type=Path), default=None)
@click.option("--pyimagej-app", type=click.Path(path_type=Path), default=None)
@click.option("--probe", is_flag=True, help="Run active probe: invoke Fiji headless plugin macro and verify marker output.")
def main(
    backend: str,
    fiji_exe: Path | None,
    fiji_macro: Path | None,
    plugin_id: str,
    plugin_jar: Path | None,
    pyimagej_app: Path | None,
    probe: bool,
) -> None:
    """Run preflight checks and exit non-zero on failure."""
    config = ThunderstormBridgeConfig(
        backend=backend,
        fiji_executable=str(fiji_exe) if fiji_exe else "",
        macro_path=str(fiji_macro) if fiji_macro else "",
        plugin_id=plugin_id,
        plugin_jar_path=str(plugin_jar) if plugin_jar else "",
        thunderstorm_jar_path=str(plugin_jar) if plugin_jar else "",
        pyimagej_app_path=str(pyimagej_app) if pyimagej_app else "",
    )
    report = run_preflight(config, probe=probe)
    click.echo(report_to_text(report))
    if not report.ok:
        raise SystemExit(int(report.exit_code or 2))


if __name__ == "__main__":
    main()
