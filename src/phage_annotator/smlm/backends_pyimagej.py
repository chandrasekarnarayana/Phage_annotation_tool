"""Smlm backends pyimagej helpers for the phage annotation tool.

This module was split from a larger implementation to keep responsibilities
small and file sizes manageable.
"""

from __future__ import annotations

import json
import os
import shlex
import subprocess
import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import Callable, Iterable, List, Optional, Tuple

import numpy as np
import pandas as pd

from phage_annotator.algorithms.smlm_thunderstorm import (
    Localization,
    SmlmParams,
    render_sr_image,
    run_smlm_stream)
from phage_annotator.io.readers.annotations import parse_thunderstorm_csv
from phage_annotator.smlm.external_plugins import (
    ExternalFijiPlugin,
    build_manifest_macro,
    build_plugin_arg_string,
    resolve_plugin_descriptor,
    resolve_plugin_jar)
from phage_annotator.smlm.backends_core_impl import (
    CSVSchemaMismatchError,
    ImageJRuntime,
    MacroExecutionError,
    OutputMissingError,
    PluginNotFoundError,
    ThunderstormBridgeConfig,
)


ProgressCb = Optional[Callable[[int, str], None]]
CancelCb = Optional[Callable[[], bool]]



def _run_fiji_pyimagej(
    materialized: List[Tuple[int, np.ndarray]],
    *,
    roi_rect: Tuple[float, float, float, float],
    params: SmlmParams,
    pixel_size_nm: Optional[float],
    config: ThunderstormBridgeConfig,
    progress_cb: ProgressCb,
    is_cancelled: CancelCb) -> Tuple[List[Localization], np.ndarray, dict]:
    """Run fiji pyimagej for the current workflow."""
    try:
        import imagej  # type: ignore  # noqa: F401
    except Exception as exc:
        raise (
            "PyImageJ backend requested but 'imagej' is not installed. "
            "Install optional dependency: pip install -e .[fiji]"
        ) from exc

    if not materialized:
        return [], np.zeros((1, 1), dtype=np.float32), {"backend": "fiji_pyimagej"}
    if is_cancelled is not None and is_cancelled():
        return [], np.zeros((1, 1), dtype=np.float32), {"backend": "fiji_pyimagej", "cancelled": True}

    app_path = config.pyimagej_app_path.strip()
    if not app_path:
        raise ("PyImageJ backend requires a local Fiji app path.")
    plugin_desc = resolve_plugin_descriptor(config.plugin_id)
    if plugin_desc is None and not (config.plugin_jar_path or config.thunderstorm_jar_path):
        raise PluginNotFoundError(
            f"Plugin '{config.plugin_id}' not discovered and no plugin JAR override provided."
        )
    plugin_params = dict(config.plugin_parameters or {})
    macro_path = str(config.macro_path or "").strip()
    if not macro_path and plugin_desc is not None and plugin_desc.macro_path:
        macro_path = plugin_desc.macro_path
    if not macro_path and not (plugin_desc is not None and plugin_desc.manifest is not None):
        raise MacroExecutionError(
            "PyImageJ backend requires a macro/script path unless selected plugin has manifest invocation."
        )

    if progress_cb is not None:
        progress_cb(10, "Initializing PyImageJ…")
    ij = ImageJRuntime.init_once(app_path)

    frame_indices = [int(idx) for idx, _ in materialized]
    frame_stack = np.stack([np.asarray(frame, dtype=np.float32) for _, frame in materialized], axis=0)
    with tempfile.TemporaryDirectory(prefix="phage_smlm_pyimagej_") as tmp_dir:
        from tifffile import imwrite

        tmp = Path(tmp_dir)
        input_tif = tmp / "input_stack.tif"
        output_csv = tmp / "thunderstorm_results.csv"
        params_json = tmp / "params.json"
        imwrite(input_tif, frame_stack.astype(np.float32, copy=False))
        params_json.write_text(json.dumps({"params": params.__dict__, "pixel_size_nm": pixel_size_nm}), encoding="utf-8")

        if macro_path:
            macro_text = Path(macro_path).read_text(encoding="utf-8")
        else:
            if plugin_desc is None or plugin_desc.manifest is None:
                raise MacroExecutionError("Unable to resolve plugin manifest macro for PyImageJ backend.")
            if plugin_desc.manifest.stack_required and len(materialized) <= 1:
                raise MacroExecutionError(
                    f"Plugin '{plugin_desc.name}' requires stack input, but current run has 1 frame."
                )
            arg_string = build_plugin_arg_string(plugin_desc, plugin_params)
            macro_text = build_manifest_macro(plugin_desc, arg_string)
        macro_text = macro_text.replace("${PHAGE_SMLM_INPUT}", str(input_tif))
        macro_text = macro_text.replace("${PHAGE_SMLM_OUTPUT}", str(output_csv))
        macro_text = macro_text.replace("${PHAGE_SMLM_PARAMS_JSON}", str(params_json))
        plugin_jar = resolve_plugin_jar(
            config.plugin_id,
            config.plugin_jar_path or config.thunderstorm_jar_path)
        plugin_id = (config.plugin_id or "").strip()
        if plugin_jar.strip():
            macro_text = macro_text.replace(
                "${PHAGE_PLUGIN_JAR}",
                plugin_jar.strip())
            macro_text = macro_text.replace(
                "${PHAGE_THUNDERSTORM_JAR}",
                plugin_jar.strip())
        if plugin_id:
            macro_text = macro_text.replace("${PHAGE_PLUGIN_ID}", plugin_id)
        if plugin_desc is not None:
            macro_text = macro_text.replace("${PHAGE_PLUGIN_NAME}", plugin_desc.name)
        if progress_cb is not None:
            progress_cb(35, "Running PyImageJ macro…")
        try:
            ij.py.run_macro(macro_text)
        except Exception as exc:
            raise MacroExecutionError(f"PyImageJ macro execution failed: {exc}") from exc
        if not output_csv.exists():
            raise OutputMissingError(
                "PyImageJ run completed without output CSV. Ensure macro writes PHAGE_SMLM_OUTPUT."
            )
        _validate_bridge_output_csv(output_csv, plugin_desc=plugin_desc)
        points = parse_thunderstorm_csv(
            output_csv,
            image_name="fiji_pyimagej",
            pixel_size_nm=pixel_size_nm,
            default_label="localization")
        locs = _keypoints_to_localizations(points, frame_indices=frame_indices)
        sr = render_sr_image(
            locs,
            roi_rect=roi_rect,
            upsample=params.upsample,
            pixel_size_nm=pixel_size_nm,
            render_mode=params.render_mode,
            render_sigma_nm=params.render_sigma_nm)
        if progress_cb is not None:
            progress_cb(100, f"PyImageJ run complete: {len(locs)} localizations")
        return locs, sr, {
            "backend": "fiji_pyimagej",
            "output_csv": str(output_csv),
            "plugin_id": plugin_id,
            "plugin_jar": plugin_jar,
            "macro_path": str(macro_path),
            "executed_macro": macro_text,
            "plugin_params": plugin_params,
        }

def _build_fiji_command(
    *,
    config: ThunderstormBridgeConfig,
    input_tif: Path,
    output_csv: Path,
    params_json: Path) -> List[str]:
    """Build fiji command for the current workflow."""
    if config.command_template.strip():
        return [
            part.format(
                fiji_executable=str(config.fiji_executable),
                macro_path=str(config.macro_path),
                input_tif=str(input_tif),
                output_csv=str(output_csv),
                params_json=str(params_json),
                plugin_id=str(config.plugin_id),
                plugin_jar_path=str(config.plugin_jar_path or config.thunderstorm_jar_path),
                thunderstorm_jar_path=str(config.thunderstorm_jar_path))
            for part in shlex.split(config.command_template)
        ]
    args = (
        f'input="{input_tif}",output="{output_csv}",params="{params_json}"'
    )
    return [
        str(config.fiji_executable),
        "--headless",
        "-macro",
        str(config.macro_path),
        args,
    ]

def _normalize_col(name: str) -> str:
    """Normalize col for the current workflow."""
    return str(name).strip().lower()

def _validate_bridge_output_csv(path: Path, *, plugin_desc: ExternalFijiPlugin | None = None) -> None:
    """Validate bridge CSV header contract before parsing localizations."""
    sep = ","
    decimal = "."
    required_cols: set[str] = set()
    if plugin_desc is not None and plugin_desc.manifest is not None:
        manifest = plugin_desc.manifest
        sep = manifest.csv_separator or ","
        decimal = manifest.csv_decimal or "."
        required_cols = {_normalize_col(c) for c in manifest.required_columns if str(c).strip()}
    try:
        df = pd.read_csv(path, nrows=0, comment="#", sep=sep, decimal=decimal)
    except Exception as exc:
        raise CSVSchemaMismatchError(f"Failed reading bridge CSV header: {exc}") from exc
    cols = {_normalize_col(c) for c in df.columns}
    if required_cols:
        missing = sorted(c for c in required_cols if c not in cols)
        if missing:
            raise CSVSchemaMismatchError(
                "Bridge CSV schema mismatch (required manifest columns missing): "
                f"{', '.join(missing)}. "
                "Try: (a) reset ThunderSTORM export settings, (b) use bundled macro, "
                "(c) run `phage-annotator-smlm-preflight --probe`."
            )
    x_ok = any(c in cols for c in {"x [px]", "x [nm]", "x(px)", "x(nm)", "x", "x_px", "x_nm"})
    y_ok = any(c in cols for c in {"y [px]", "y [nm]", "y(px)", "y(nm)", "y", "y_px", "y_nm"})
    if not (x_ok and y_ok):
        raise CSVSchemaMismatchError(
            "Bridge CSV missing required coordinate columns (x/y). "
            "Ensure macro exports ThunderSTORM-compatible table schema. "
            "Try: (a) reset ThunderSTORM export settings, (b) use bundled macro, "
            "(c) run `phage-annotator-smlm-preflight --probe`."
        )

def _keypoints_to_localizations(points, *, frame_indices: List[int]) -> List[Localization]:
    """Handle the keypoints to localizations helper flow."""
    locs: List[Localization] = []
    frame_map = {idx: n for n, idx in enumerate(sorted(set(frame_indices)))}
    for point in points:
        meta = dict(getattr(point, "meta", {}) or {})
        t_raw = int(getattr(point, "t", -1))
        frame_idx = frame_map.get(t_raw, max(t_raw, 0))
        locs.append(
            Localization(
                frame_index=int(frame_idx),
                x_px=float(getattr(point, "x", 0.0)),
                y_px=float(getattr(point, "y", 0.0)),
                sigma_px=float(meta.get("sigma [px]", meta.get("sigma_px", 1.0))),
                photons=float(meta.get("intensity [photon]", meta.get("photons", 0.0))),
                background=float(meta.get("offset [photon]", meta.get("background", 0.0))),
                uncertainty_px=float(meta.get("uncertainty [px]", meta.get("uncertainty_px", 0.25))),
                label=str(getattr(point, "label", "localization")))
        )
    return locs
