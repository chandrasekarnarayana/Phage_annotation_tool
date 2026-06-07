"""Smlm backends core helpers for the phage annotation tool.

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


ProgressCb = Optional[Callable[[int, str], None]]
CancelCb = Optional[Callable[[], bool]]

from phage_annotator.smlm import backends_core_impl as _core_impl
from phage_annotator.smlm.backends_core_impl import (
    CSVSchemaMismatchError,
    FijiNotFoundError,
    FijiTimeoutError,
    ImageJRuntime,
    MacroExecutionError,
    OutputMissingError,
    PluginNotFoundError,
    SmlmBridgeError,
    ThunderstormBridgeConfig,
    run_thunderstorm_backend,
)
from phage_annotator.smlm.backends_pyimagej import (
    _build_fiji_command,
    _keypoints_to_localizations,
    _normalize_col,
    _run_fiji_pyimagej,
    _validate_bridge_output_csv,
)
from phage_annotator.smlm.backends_subprocess import _run_fiji_subprocess

_core_impl._run_fiji_subprocess = _run_fiji_subprocess
_core_impl._run_fiji_pyimagej = _run_fiji_pyimagej
