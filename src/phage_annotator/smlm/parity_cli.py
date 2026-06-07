"""CLI for SMLM parity checks between internal and ThunderSTORM outputs."""

from __future__ import annotations

import json
from pathlib import Path

import click

from phage_annotator.algorithms.smlm_thunderstorm import Localization
from phage_annotator.io.readers.annotations import parse_thunderstorm_csv
from phage_annotator.smlm.parity import compute_parity_metrics


def _to_locs(points) -> list[Localization]:
    """Convert locs for the current workflow."""
    locs: list[Localization] = []
    for point in points:
        meta = dict(getattr(point, "meta", {}) or {})
        locs.append(
            Localization(
                frame_index=max(int(getattr(point, "t", 0)), 0),
                x_px=float(getattr(point, "x", 0.0)),
                y_px=float(getattr(point, "y", 0.0)),
                sigma_px=float(meta.get("sigma [px]", meta.get("sigma_px", 1.0))),
                photons=float(meta.get("intensity [photon]", meta.get("photons", 0.0))),
                background=float(meta.get("offset [photon]", meta.get("background", 0.0))),
                uncertainty_px=float(meta.get("uncertainty [px]", meta.get("uncertainty_px", 0.25))),
            )
        )
    return locs


@click.command(context_settings={"help_option_names": ["-h", "--help"]})
@click.option("--internal-csv", type=click.Path(path_type=Path, exists=True), required=True)
@click.option("--thunderstorm-csv", type=click.Path(path_type=Path, exists=True), required=True)
@click.option("--pixel-size-nm", type=float, default=None)
@click.option("--tolerance-px", type=float, default=1.5, show_default=True)
@click.option("--out-json", type=click.Path(path_type=Path), default=None)
def main(
    internal_csv: Path,
    thunderstorm_csv: Path,
    pixel_size_nm: float | None,
    tolerance_px: float,
    out_json: Path | None,
) -> None:
    """Compute parity metrics from two localization CSV files."""
    internal_points = parse_thunderstorm_csv(
        internal_csv,
        image_name=internal_csv.stem,
        pixel_size_nm=pixel_size_nm,
        default_label="internal",
    )
    bridge_points = parse_thunderstorm_csv(
        thunderstorm_csv,
        image_name=thunderstorm_csv.stem,
        pixel_size_nm=pixel_size_nm,
        default_label="bridge",
    )
    metrics = compute_parity_metrics(
        _to_locs(internal_points),
        _to_locs(bridge_points),
        tolerance_px=tolerance_px,
    )
    payload = {
        "internal_count": metrics.internal_count,
        "bridge_count": metrics.bridge_count,
        "matched_count": metrics.matched_count,
        "precision": metrics.precision,
        "recall": metrics.recall,
        "mean_xy_error_px": metrics.mean_xy_error_px,
        "median_xy_error_px": metrics.median_xy_error_px,
        "tolerance_px": tolerance_px,
    }
    text = json.dumps(payload, indent=2)
    click.echo(text)
    if out_json is not None:
        out_json.parent.mkdir(parents=True, exist_ok=True)
        out_json.write_text(text + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
