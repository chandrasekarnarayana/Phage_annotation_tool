"""SMLM backend adapters (internal and Fiji/ThunderSTORM bridge modes)."""

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
    run_smlm_stream,
)
from phage_annotator.io.readers.annotations import parse_thunderstorm_csv
from phage_annotator.smlm.external_plugins import (
    ExternalFijiPlugin,
    build_manifest_macro,
    build_plugin_arg_string,
    resolve_plugin_descriptor,
    resolve_plugin_jar,
)


ProgressCb = Optional[Callable[[int, str], None]]
CancelCb = Optional[Callable[[], bool]]


class SmlmBridgeError(RuntimeError):
    """Base class for SMLM bridge failures with remediation hints."""


class FijiNotFoundError(SmlmBridgeError):
    """Raised when Fiji executable/app path is missing."""


class PluginNotFoundError(SmlmBridgeError):
    """Raised when plugin id/JAR cannot be resolved."""


class MacroExecutionError(SmlmBridgeError):
    """Raised when macro execution fails."""


class OutputMissingError(SmlmBridgeError):
    """Raised when bridge execution does not produce required artifacts."""


class CSVSchemaMismatchError(SmlmBridgeError):
    """Raised when output CSV schema is incompatible with parser contract."""


class FijiTimeoutError(SmlmBridgeError):
    """Raised when Fiji execution exceeds configured timeout."""


class ImageJRuntime:
    """Singleton runtime for PyImageJ initialization within a session."""

    _ij = None
    _app_path = ""

    @classmethod
    def init_once(cls, app_path: str):
        """Initialize or reuse PyImageJ runtime for app path."""
        normalized = str(app_path).strip()
        if cls._ij is not None and cls._app_path == normalized:
            return cls._ij
        import imagej  # type: ignore

        cls._ij = imagej.init(normalized, mode="headless")
        cls._app_path = normalized
        return cls._ij


@dataclass(frozen=True)
class ThunderstormBridgeConfig:
    """Configuration for bridge execution through Fiji/ImageJ."""

    backend: str = "internal"  # internal | fiji_subprocess | fiji_pyimagej
    fiji_executable: str = ""
    macro_path: str = ""
    plugin_id: str = "thunder_storm"
    plugin_jar_path: str = ""
    plugin_parameters: dict = None
    thunderstorm_jar_path: str = ""
    command_template: str = ""
    pyimagej_app_path: str = ""
    timeout_sec: int = 900


def discover_bundled_thunderstorm_jar(start_dir: Optional[Path] = None) -> Optional[Path]:
    """Locate a bundled ThunderSTORM JAR in common project locations."""
    candidates = ("Thunder_STORM.jar", "ThunderSTORM.jar", "thunder_storm.jar")
    roots: List[Path] = []
    if start_dir is not None:
        roots.append(Path(start_dir))
    roots.append(Path.cwd())
    # src/phage_annotator/smlm/backends.py -> repo root is parents[3]
    roots.append(Path(__file__).resolve().parents[3])
    for root in roots:
        plugin_dir = root / "external_plugins"
        for name in candidates:
            jar = plugin_dir / name
            if jar.exists() and jar.is_file():
                return jar.resolve()
    return None


def run_thunderstorm_backend(
    frames: Iterable[Tuple[int, np.ndarray]],
    *,
    total_frames: int,
    roi_mask: Optional[np.ndarray],
    roi_rect: Tuple[float, float, float, float],
    crop_offset: Tuple[int, int],
    params: SmlmParams,
    pixel_size_nm: Optional[float],
    config: ThunderstormBridgeConfig,
    progress_cb: ProgressCb = None,
    is_cancelled: CancelCb = None,
) -> Tuple[List[Localization], np.ndarray, dict]:
    """Run SMLM using configured backend and return normalized outputs."""
    backend = (config.backend or "internal").strip().lower()
    if backend == "internal":
        locs, sr = run_smlm_stream(
            frames,
            total_frames=total_frames,
            roi_mask=roi_mask,
            roi_rect=roi_rect,
            crop_offset=crop_offset,
            params=params,
            pixel_size_nm=pixel_size_nm,
            progress_cb=progress_cb,
            is_cancelled=is_cancelled,
        )
        return locs, sr, {"backend": "internal"}

    materialized: List[Tuple[int, np.ndarray]] = list(frames)
    if backend == "fiji_subprocess":
        return _run_fiji_subprocess(
            materialized,
            roi_rect=roi_rect,
            params=params,
            pixel_size_nm=pixel_size_nm,
            config=config,
            progress_cb=progress_cb,
            is_cancelled=is_cancelled,
        )
    if backend == "fiji_pyimagej":
        return _run_fiji_pyimagej(
            materialized,
            roi_rect=roi_rect,
            params=params,
            pixel_size_nm=pixel_size_nm,
            config=config,
            progress_cb=progress_cb,
            is_cancelled=is_cancelled,
        )
    raise ValueError(f"Unsupported SMLM backend: {config.backend}")


def _run_fiji_subprocess(
    materialized: List[Tuple[int, np.ndarray]],
    *,
    roi_rect: Tuple[float, float, float, float],
    params: SmlmParams,
    pixel_size_nm: Optional[float],
    config: ThunderstormBridgeConfig,
    progress_cb: ProgressCb,
    is_cancelled: CancelCb,
) -> Tuple[List[Localization], np.ndarray, dict]:
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
        command = _build_fiji_command(
            config=ThunderstormBridgeConfig(
                backend=config.backend,
                fiji_executable=config.fiji_executable,
                macro_path=macro_path,
                plugin_id=config.plugin_id,
                plugin_jar_path=config.plugin_jar_path,
                thunderstorm_jar_path=config.thunderstorm_jar_path,
                command_template=config.command_template,
                pyimagej_app_path=config.pyimagej_app_path,
                timeout_sec=config.timeout_sec,
                plugin_parameters=config.plugin_parameters,
            ),
            input_tif=input_tif,
            output_csv=output_csv,
            params_json=params_json,
        )
        env = os.environ.copy()
        env.setdefault("PHAGE_SMLM_INPUT", str(input_tif))
        env.setdefault("PHAGE_SMLM_OUTPUT", str(output_csv))
        env.setdefault("PHAGE_SMLM_PARAMS_JSON", str(params_json))
        plugin_jar = resolve_plugin_jar(
            config.plugin_id,
            config.plugin_jar_path or config.thunderstorm_jar_path,
        )
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
        try:
            proc = subprocess.run(
                command,
                check=False,
                capture_output=True,
                text=True,
                timeout=max(30, int(config.timeout_sec)),
                env=env,
            )
        except subprocess.TimeoutExpired as exc:
            raise FijiTimeoutError(
                "Fiji run timed out. Increase timeout or reduce ROI/stack size."
            ) from exc
        if proc.returncode != 0:
            stderr = (proc.stderr or "").strip()
            stdout = (proc.stdout or "").strip()
            detail = stderr or stdout or f"exit={proc.returncode}"
            raise MacroExecutionError(
                "Fiji bridge failed. Check macro/plugin compatibility. "
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
            default_label="localization",
        )
        locs = _keypoints_to_localizations(points, frame_indices=frame_indices)
        sr = render_sr_image(
            locs,
            roi_rect=roi_rect,
            upsample=params.upsample,
            pixel_size_nm=pixel_size_nm,
            render_mode=params.render_mode,
            render_sigma_nm=params.render_sigma_nm,
        )
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
        }


def _run_fiji_pyimagej(
    materialized: List[Tuple[int, np.ndarray]],
    *,
    roi_rect: Tuple[float, float, float, float],
    params: SmlmParams,
    pixel_size_nm: Optional[float],
    config: ThunderstormBridgeConfig,
    progress_cb: ProgressCb,
    is_cancelled: CancelCb,
) -> Tuple[List[Localization], np.ndarray, dict]:
    try:
        import imagej  # type: ignore  # noqa: F401
    except Exception as exc:
        raise FijiNotFoundError(
            "PyImageJ backend requested but 'imagej' is not installed. "
            "Install optional dependency: pip install -e .[fiji]"
        ) from exc

    if not materialized:
        return [], np.zeros((1, 1), dtype=np.float32), {"backend": "fiji_pyimagej"}
    if is_cancelled is not None and is_cancelled():
        return [], np.zeros((1, 1), dtype=np.float32), {"backend": "fiji_pyimagej", "cancelled": True}

    app_path = config.pyimagej_app_path.strip()
    if not app_path:
        raise FijiNotFoundError("PyImageJ backend requires a local Fiji app path.")
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
            config.plugin_jar_path or config.thunderstorm_jar_path,
        )
        plugin_id = (config.plugin_id or "").strip()
        if plugin_jar.strip():
            macro_text = macro_text.replace(
                "${PHAGE_PLUGIN_JAR}",
                plugin_jar.strip(),
            )
            macro_text = macro_text.replace(
                "${PHAGE_THUNDERSTORM_JAR}",
                plugin_jar.strip(),
            )
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
            default_label="localization",
        )
        locs = _keypoints_to_localizations(points, frame_indices=frame_indices)
        sr = render_sr_image(
            locs,
            roi_rect=roi_rect,
            upsample=params.upsample,
            pixel_size_nm=pixel_size_nm,
            render_mode=params.render_mode,
            render_sigma_nm=params.render_sigma_nm,
        )
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
    params_json: Path,
) -> List[str]:
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
                thunderstorm_jar_path=str(config.thunderstorm_jar_path),
            )
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
                label=str(getattr(point, "label", "localization")),
            )
        )
    return locs
