"""Smoke-test CLI for SMLM/Fiji bridge demo runs."""

from __future__ import annotations

import csv
import hashlib
import json
from pathlib import Path

import click
import numpy as np
from tifffile import imwrite

from phage_annotator.algorithms.smlm_thunderstorm import SmlmParams
from phage_annotator.smlm.backends import (
    CSVSchemaMismatchError,
    FijiNotFoundError,
    FijiTimeoutError,
    MacroExecutionError,
    OutputMissingError,
    PluginNotFoundError,
    ThunderstormBridgeConfig,
    run_thunderstorm_backend,
)
from phage_annotator.smlm.external_plugins import resolve_plugin_descriptor, resolve_plugin_jar
from phage_annotator.smlm.preflight import report_to_text, run_preflight


def _synthetic_frames() -> list[tuple[int, np.ndarray]]:
    """Handle the synthetic frames helper flow."""
    rng = np.random.default_rng(19)
    frames: list[tuple[int, np.ndarray]] = []
    for t in range(4):
        frame = rng.normal(12.0, 1.4, size=(64, 64)).astype(np.float32)
        frame[16 + t, 20 + t] += 80.0
        frame[48 - t, 42] += 65.0
        frames.append((t, frame))
    return frames


def _exit_code_from_exc(exc: Exception) -> int:
    """Handle the exit code from exc helper flow."""
    if isinstance(exc, FijiNotFoundError):
        return 2
    if isinstance(exc, PluginNotFoundError):
        return 3
    if isinstance(exc, (MacroExecutionError, FijiTimeoutError)):
        return 4
    if isinstance(exc, (OutputMissingError, CSVSchemaMismatchError)):
        return 5
    return 1


def _sha256(path: Path) -> str:
    """Handle the sha256 helper flow."""
    h = hashlib.sha256()
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(8192), b""):
            h.update(chunk)
    return h.hexdigest()


@click.command(context_settings={"help_option_names": ["-h", "--help"]})
@click.option("--backend", type=click.Choice(["internal", "fiji_subprocess", "fiji_pyimagej"]), default="internal")
@click.option("--plugin-id", type=str, default="thunder_storm")
@click.option("--plugin-jar", type=click.Path(path_type=Path), default=None)
@click.option("--fiji-exe", type=click.Path(path_type=Path), default=None)
@click.option("--fiji-macro", type=click.Path(path_type=Path), default=None)
@click.option("--pyimagej-app", type=click.Path(path_type=Path), default=None)
@click.option("--out-dir", type=click.Path(path_type=Path), default=Path("artifacts") / "smlm_demo")
@click.option("--probe-first", is_flag=True, help="Run preflight probe before executing demo.")
def main(
    backend: str,
    plugin_id: str,
    plugin_jar: Path | None,
    fiji_exe: Path | None,
    fiji_macro: Path | None,
    pyimagej_app: Path | None,
    out_dir: Path,
    probe_first: bool,
) -> None:
    """Run a tiny deterministic SMLM demo and export artifacts."""
    out_dir.mkdir(parents=True, exist_ok=True)
    config = ThunderstormBridgeConfig(
        backend=backend,
        plugin_id=plugin_id,
        plugin_jar_path=str(plugin_jar) if plugin_jar else "",
        thunderstorm_jar_path=str(plugin_jar) if plugin_jar else "",
        fiji_executable=str(fiji_exe) if fiji_exe else "",
        macro_path=str(fiji_macro) if fiji_macro else "",
        pyimagej_app_path=str(pyimagej_app) if pyimagej_app else "",
        timeout_sec=180,
    )
    if probe_first:
        report = run_preflight(config, probe=True)
        click.echo(report_to_text(report))
        if not report.ok:
            raise SystemExit(int(report.exit_code or 2))

    frames = _synthetic_frames()
    params = SmlmParams(
        detection_thr_sigma=1.8,
        min_photons=0.0,
        max_candidates_per_frame=10000,
    )
    try:
        locs, sr, meta = run_thunderstorm_backend(
            frames,
            total_frames=len(frames),
            roi_mask=np.ones((64, 64), dtype=bool),
            roi_rect=(0.0, 0.0, 64.0, 64.0),
            crop_offset=(0, 0),
            params=params,
            pixel_size_nm=100.0,
            config=config,
            progress_cb=None,
            is_cancelled=None,
        )
    except Exception as exc:
        click.echo(f"Demo run failed: {exc}")
        raise SystemExit(_exit_code_from_exc(exc))

    csv_path = out_dir / "demo_localizations.csv"
    with csv_path.open("w", newline="", encoding="utf-8") as fh:
        writer = csv.writer(fh)
        writer.writerow(["frame_index", "x_px", "y_px", "sigma_px", "photons", "background", "uncertainty_px"])
        for loc in locs:
            writer.writerow(
                [
                    int(loc.frame_index),
                    float(loc.x_px),
                    float(loc.y_px),
                    float(loc.sigma_px),
                    float(loc.photons),
                    float(loc.background),
                    float(loc.uncertainty_px),
                ]
            )
    sr_path = out_dir / "demo_sr.tif"
    imwrite(sr_path, np.asarray(sr, dtype=np.float32))
    resolved_plugin_jar = resolve_plugin_jar(plugin_id, str(plugin_jar) if plugin_jar else "")
    plugin_desc = resolve_plugin_descriptor(plugin_id)
    run_manifest = {
        "backend": backend,
        "plugin_id": plugin_id,
        "plugin_jar": resolved_plugin_jar,
        "plugin_jar_sha256": _sha256(Path(resolved_plugin_jar)) if resolved_plugin_jar and Path(resolved_plugin_jar).exists() else "",
        "manifest_path": plugin_desc.manifest_path if plugin_desc is not None else "",
        "plugin_version_tested": plugin_desc.manifest.plugin_version_tested
        if plugin_desc is not None and plugin_desc.manifest is not None
        else "",
        "csv_schema_version": plugin_desc.manifest.csv_schema_version
        if plugin_desc is not None and plugin_desc.manifest is not None
        else "",
        "detections": int(len(locs)),
        "artifacts": {
            "csv": str(csv_path),
            "sr_tif": str(sr_path),
        },
    }
    manifest_path = out_dir / "run_manifest.json"
    manifest_path.write_text(json.dumps(run_manifest, indent=2), encoding="utf-8")
    checksum_path = out_dir / "sha256sums.txt"
    checksum_lines = [
        f"{_sha256(csv_path)}  {csv_path.name}",
        f"{_sha256(sr_path)}  {sr_path.name}",
        f"{_sha256(manifest_path)}  {manifest_path.name}",
    ]
    checksum_path.write_text("\n".join(checksum_lines) + "\n", encoding="utf-8")
    click.echo(f"Demo completed with {len(locs)} detections.")
    click.echo(f"CSV: {csv_path}")
    click.echo(f"SR: {sr_path}")
    click.echo(f"Manifest: {manifest_path}")
    click.echo(f"Checksums: {checksum_path}")
    if meta:
        click.echo(f"Backend meta: {meta}")


if __name__ == "__main__":
    main()
