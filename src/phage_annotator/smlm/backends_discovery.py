"""Smlm backends discovery helpers for the phage annotation tool.

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
