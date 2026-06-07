"""Method group 2 split from smlm_controls_runbook.py."""

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

class _SmlmControlsRunbookMixinMethods2:
    """Methods split from SmlmControlsRunbookMixin."""

    def _lock_current_smlm_profile(self) -> None:
        """Document the lock_current_smlm_profile flow."""
        if self.smlm_panel is None:
            return
        params = self._smlm_params_from_ui()
        if params is None:
            return
        bridge = self._smlm_bridge_config_from_ui()
        state = self._get_runbook_state()
        lock_profile(
            state,
            "ThunderSTORM",
            {
                "backend": bridge.backend,
                "plugin_id": bridge.plugin_id,
                "plugin_jar_path": bridge.plugin_jar_path,
                "params": dict(params.__dict__),
                "fiji_executable": bridge.fiji_executable,
                "fiji_macro_path": bridge.macro_path,
                "thunderstorm_jar_path": bridge.thunderstorm_jar_path,
                "fiji_command_template": bridge.command_template,
                "pyimagej_app_path": bridge.pyimagej_app_path,
            },
        )
        self._sync_runbook_state_to_session()
        self._status_success(
            "Runbook profile locked for ThunderSTORM.",
            timeout_ms=3000,
            source="smlm.runbook.lock",
        )
        self.smlm_panel.thunder.status_label.setText("Runbook profile locked.")

    def _export_smlm_runbook(self) -> None:
        """Document the export_smlm_runbook flow."""
        state = self._get_runbook_state()
        path, _ = QtWidgets.QFileDialog.getSaveFileName(
            self,
            "Export Reproducibility Runbook",
            str(pathlib.Path.cwd() / "smlm_runbook.json"),
            "JSON Files (*.json)",
        )
        if not path:
            return
        out = export_reproducibility_bundle(
            state,
            out_path=pathlib.Path(path),
            session_payload={
                "image_path": str(getattr(self.primary_image, "path", "")),
                "smlm_runs": list(getattr(self, "_smlm_run_history", [])),
            },
        )
        self._sync_runbook_state_to_session()
        self._status_success(
            f"Exported runbook to {out}",
            timeout_ms=4000,
            source="smlm.runbook.export",
        )
        if self.smlm_panel is not None:
            self.smlm_panel.thunder.status_label.setText(f"Runbook exported: {out.name}")
