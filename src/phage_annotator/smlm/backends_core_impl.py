"""Smlm backends core impl helpers for the phage annotation tool.

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
from typing import Callable, Iterable, List, Optional, Tuple, TYPE_CHECKING

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

if TYPE_CHECKING:
    # Runtime bindings for _run_fiji_subprocess/_run_fiji_pyimagej are
    # injected by phage_annotator.smlm.backends_core (which imports this
    # module along with backends_subprocess/backends_pyimagej) to avoid a
    # circular import; this import is for static analysis only.
    from phage_annotator.smlm.backends_subprocess import _run_fiji_subprocess
    from phage_annotator.smlm.backends_pyimagej import _run_fiji_pyimagej


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
    retry_count: int = 1
    retry_delay_sec: float = 0.75

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
    is_cancelled: CancelCb = None) -> Tuple[List[Localization], np.ndarray, dict]:
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
            is_cancelled=is_cancelled)
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
            is_cancelled=is_cancelled)
    if backend == "fiji_pyimagej":
        return _run_fiji_pyimagej(
            materialized,
            roi_rect=roi_rect,
            params=params,
            pixel_size_nm=pixel_size_nm,
            config=config,
            progress_cb=progress_cb,
            is_cancelled=is_cancelled)
    raise ValueError(f"Unsupported SMLM backend: {config.backend}")
