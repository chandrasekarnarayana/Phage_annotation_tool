"""Extracted method group 7 for SmlmControlsMixin."""

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



class SmlmControlsExportMixin:
    """Method group 7 extracted from SmlmControlsMixin."""

    def _build_plugin_parameters(self, params: SmlmParams) -> dict:
        """Map current SMLM parameters into plugin manifest parameter names."""
        return {
            "sigma_px": float(params.sigma_px),
            "fit_radius_px": int(params.fit_radius_px),
            "filter_type": str(params.filter_type),
            "dog_sigma1": float(params.dog_sigma1),
            "dog_sigma2": float(params.dog_sigma2),
            "detection_thr_sigma": float(params.detection_thr_sigma),
            "max_candidates_per_frame": int(params.max_candidates_per_frame),
            "merge_radius_px": float(params.merge_radius_px),
            "min_photons": float(params.min_photons),
            "max_uncertainty_nm": float(params.max_uncertainty_nm),
            "upsample": int(params.upsample),
            "render_mode": str(params.render_mode),
            "render_sigma_nm": float(params.render_sigma_nm),
        }
    def _on_smlm_runbook_toggled(self, checked: bool) -> None:
        """Handle the on smlm runbook toggled helper flow."""
        state = self._get_runbook_state()
        state.enabled = bool(checked)
        append_provenance_event(
            state,
            event_type="runbook_toggled",
            payload={"enabled": bool(checked)},
        )
        self._sync_runbook_state_to_session()
        self._status_info(
            "SMLM runbook mode enabled." if checked else "SMLM runbook mode disabled.",
            timeout_ms=2500,
            source="smlm.runbook.toggle",
        )
