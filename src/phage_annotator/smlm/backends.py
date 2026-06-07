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
ProgressCb = Optional[Callable[[int, str], None]]
CancelCb = Optional[Callable[[], bool]]


from phage_annotator.smlm.backends_core import SmlmBridgeError, FijiNotFoundError, PluginNotFoundError, MacroExecutionError, OutputMissingError, CSVSchemaMismatchError, FijiTimeoutError, ImageJRuntime, ThunderstormBridgeConfig, run_thunderstorm_backend, _run_fiji_subprocess, _run_fiji_pyimagej, _build_fiji_command, _normalize_col, _validate_bridge_output_csv, _keypoints_to_localizations
from phage_annotator.smlm.backends_discovery import discover_bundled_thunderstorm_jar
