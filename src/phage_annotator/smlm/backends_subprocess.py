"""Smlm backends subprocess helpers for the phage annotation tool.

This module was split from a larger implementation to keep responsibilities
small and file sizes manageable.
"""

from __future__ import annotations

import json
import os
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
from phage_annotator.smlm.backends_pyimagej import (
    _keypoints_to_localizations,
    _validate_bridge_output_csv,
)
from phage_annotator.smlm.backends_core_impl import (
    FijiNotFoundError,
    PluginNotFoundError,
    MacroExecutionError,
    OutputMissingError,
    FijiTimeoutError,
    ThunderstormBridgeConfig,
)
from phage_annotator.smlm.platform_utils import split_command_template, build_fiji_headless_command


ProgressCb = Optional[Callable[[int, str], None]]
CancelCb = Optional[Callable[[], bool]]



def _run_fiji_subprocess(
    materialized: List[Tuple[int, np.ndarray]],
    *,
    roi_rect: Tuple[float, float, float, float],
    params: SmlmParams,
    pixel_size_nm: Optional[float],
    config: ThunderstormBridgeConfig,
    progress_cb: ProgressCb,
    is_cancelled: CancelCb) -> Tuple[List[Localization], np.ndarray, dict]:
    """Run fiji subprocess for the current workflow."""
    if not materialized:
        return [], np.zeros((1, 1), dtype=np.float32), {"backend": "fiji_subprocess"}
    if is_cancelled is not None and is_cancelled():
        return [], np.zeros((1, 1), dtype=np.float32), {"backend": "fiji_subprocess", "cancelled": True}
    if not config.fiji_executable:
        raise FijiNotFoundError(
            "Fiji executable path is required for fiji_subprocess backend. "
            "Set SMLM -> Advanced Bridge -> Fiji executable."
        )
    plugin_desc = resolve_plugin_descriptor(config.plugin_id)
    if plugin_desc is None and not (config.plugin_jar_path or config.thunderstorm_jar_path):
        raise PluginNotFoundError(
            f"Plugin '{config.plugin_id}' not discovered and no plugin JAR override provided."
        )
    plugin_params = dict(config.plugin_parameters or {})
    macro_path = str(config.macro_path or "").strip()
    if not macro_path and plugin_desc is not None and plugin_desc.macro_path:
        macro_path = plugin_desc.macro_path
    if not macro_path and plugin_desc is not None and plugin_desc.manifest is not None:
        if plugin_desc.manifest.stack_required and len(materialized) <= 1:
            raise MacroExecutionError(
                f"Plugin '{plugin_desc.name}' requires stack input, but current run has 1 frame."
            )
    elif not macro_path:
        raise MacroExecutionError(
            "Fiji macro/script path is required unless selected plugin provides strict manifest invocation."
        )
    if macro_path and not Path(macro_path).exists():
        raise MacroExecutionError(f"Fiji macro not found: {macro_path}")

    if progress_cb is not None:
        progress_cb(5, "Preparing Fiji bridge run…")

    frame_indices = [int(idx) for idx, _ in materialized]
    frame_stack = np.stack([np.asarray(frame, dtype=np.float32) for _, frame in materialized], axis=0)

    with tempfile.TemporaryDirectory(prefix="phage_smlm_bridge_") as tmp_dir:
        from tifffile import imwrite

        tmp = Path(tmp_dir)
        input_tif = tmp / "input_stack.tif"
        output_csv = tmp / "thunderstorm_results.csv"
        params_json = tmp / "params.json"
        imwrite(input_tif, frame_stack.astype(np.float32, copy=False))
        params_json.write_text(json.dumps({"params": params.__dict__, "pixel_size_nm": pixel_size_nm}), encoding="utf-8")

        temp_macro: Path | None = None
        executed_macro_text = ""
        if not macro_path and plugin_desc is not None and plugin_desc.manifest is not None:
            arg_string = build_plugin_arg_string(plugin_desc, plugin_params)
            executed_macro_text = build_manifest_macro(plugin_desc, arg_string)
            temp_macro = tmp / "generated_manifest.ijm"
            temp_macro.write_text(executed_macro_text, encoding="utf-8")
            macro_path = str(temp_macro)
        if config.command_template:
            command = split_command_template(config.command_template)
            command = [c.replace("{macro_path}", str(macro_path or "")).replace("{fiji}", config.fiji_executable) for c in command]
        else:
            command = build_fiji_headless_command(config.fiji_executable, str(macro_path or ""))
        env = os.environ.copy()
        env.setdefault("PHAGE_SMLM_INPUT", str(input_tif))
        env.setdefault("PHAGE_SMLM_OUTPUT", str(output_csv))
        env.setdefault("PHAGE_SMLM_PARAMS_JSON", str(params_json))
        plugin_jar = resolve_plugin_jar(
            config.plugin_id,
            config.plugin_jar_path or config.thunderstorm_jar_path)
        jar_path = plugin_jar.strip()
        if jar_path:
            env.setdefault("PHAGE_PLUGIN_JAR", jar_path)
            env.setdefault("PHAGE_THUNDERSTORM_JAR", jar_path)  # backward compatibility
        plugin_id = (config.plugin_id or "").strip()
        if plugin_id:
            env.setdefault("PHAGE_PLUGIN_ID", plugin_id)
        if plugin_desc is not None:
            env.setdefault("PHAGE_PLUGIN_NAME", plugin_desc.name)
            for key, value in plugin_desc.env.items():
                env.setdefault(str(key), str(value))
            if plugin_desc.manifest is not None:
                env.setdefault("PHAGE_PLUGIN_COMMAND", plugin_desc.manifest.run_command)
                env.setdefault("PHAGE_PLUGIN_MENU_PATH", plugin_desc.manifest.menu_path)

        if progress_cb is not None:
            progress_cb(20, "Running Fiji/ThunderSTORM…")
        attempts = max(1, int(getattr(config, "retry_count", 1)) + 1)
        retry_delay = max(0.0, float(getattr(config, "retry_delay_sec", 0.75)))
        proc = None
        timeout_error = None
        import time as _time
        for attempt in range(1, attempts + 1):
            try:
                proc = subprocess.run(
                    command,
                    check=False,
                    capture_output=True,
                    text=True,
                    timeout=max(30, int(config.timeout_sec)),
                    env=env)
                timeout_error = None
            except subprocess.TimeoutExpired as exc:
                proc = None
                timeout_error = exc
                if attempt < attempts:
                    if progress_cb is not None:
                        progress_cb(
                            20,
                            f"Fiji attempt {attempt}/{attempts} timed out; retrying…")
                    _time.sleep(retry_delay)
                    continue
                raise FijiTimeoutError(
                    "Fiji run timed out after retry attempts. "
                    "Increase timeout or reduce ROI/stack size."
                ) from exc

            if proc is not None and proc.returncode == 0:
                break
            if attempt < attempts:
                if progress_cb is not None:
                    progress_cb(
                        20,
                        f"Fiji attempt {attempt}/{attempts} failed; retrying…")
                _time.sleep(retry_delay)
        if timeout_error is not None:
            raise FijiTimeoutError(
                "Fiji run timed out after retry attempts. "
                "Increase timeout or reduce ROI/stack size."
            ) from timeout_error
        if proc is None:
            raise MacroExecutionError("Fiji bridge failed before subprocess execution.")
        if proc.returncode != 0:
            stderr = (proc.stderr or "").strip()
            stdout = (proc.stdout or "").strip()
            detail = stderr or stdout or f"exit={proc.returncode}"
            raise MacroExecutionError(
                "Fiji bridge failed after retry attempts. Check macro/plugin compatibility. "
                f"Details: {detail}"
            )
        if not output_csv.exists():
            raise OutputMissingError(
                "Fiji bridge completed without output CSV. Ensure macro writes PHAGE_SMLM_OUTPUT."
            )
        _validate_bridge_output_csv(output_csv, plugin_desc=plugin_desc)

        if progress_cb is not None:
            progress_cb(75, "Parsing ThunderSTORM output…")
        points = parse_thunderstorm_csv(
            output_csv,
            image_name="fiji_bridge",
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
            progress_cb(100, f"Fiji run complete: {len(locs)} localizations")
        return locs, sr, {
            "backend": "fiji_subprocess",
            "output_csv": str(output_csv),
            "plugin_id": plugin_id,
            "plugin_jar": jar_path,
            "macro_path": str(macro_path),
            "executed_macro": executed_macro_text,
            "plugin_params": plugin_params,
            "retry_count": int(getattr(config, "retry_count", 1)),
        }
