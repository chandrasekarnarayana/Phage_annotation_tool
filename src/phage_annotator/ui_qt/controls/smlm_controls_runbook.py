"""SMLM (ThunderSTORM/Deep-STORM) handlers."""

from __future__ import annotations

import csv
import hashlib
import importlib.metadata
import pathlib
import platform
import subprocess
import sys
import textwrap
from datetime import datetime
from typing import Optional, Tuple

import numpy as np
from matplotlib.backends.qt_compat import QtCore, QtGui, QtWidgets

from phage_annotator.analysis.core import roi_mask_for_shape
from phage_annotator.deepstorm.infer import DeepStormParams, is_torch_available, run_deepstorm_stream
from phage_annotator.smlm.backends import (
    ThunderstormBridgeConfig,
    discover_bundled_thunderstorm_jar,
    run_thunderstorm_backend,
)
from phage_annotator.smlm.reproducibility import (
    ReproducibilityRunbookState,
    append_provenance_event,
    export_reproducibility_bundle,
    lock_profile,
    resolve_profile,
)
from phage_annotator.smlm.preflight import report_to_text, run_preflight
from phage_annotator.smlm.external_plugins import parse_plugins_config_from_jar
from phage_annotator.smlm.thunderstorm import SmlmParams

from phage_annotator.ui_qt.controls.smlm_controls_runbook_methods1 import _SmlmControlsRunbookMixinMethods1
from phage_annotator.ui_qt.controls.smlm_controls_runbook_methods2 import _SmlmControlsRunbookMixinMethods2

class SmlmControlsRunbookMixin(_SmlmControlsRunbookMixinMethods1, _SmlmControlsRunbookMixinMethods2):
    """Runbook state, preflight checks, and run execution."""

    pass
