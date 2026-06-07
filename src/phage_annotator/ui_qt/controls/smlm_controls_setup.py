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

class SmlmControlsSetupMixin:
    """Fiji/DeepSTORM path selection and plugin management."""

    def _pick_smlm_fiji_app_path(self) -> None:
        """Document the pick_smlm_fiji_app_path flow."""
        if self.smlm_panel is None:
            return
        path = QtWidgets.QFileDialog.getExistingDirectory(self, "Select Fiji.app directory")
        if path:
            self.smlm_panel.thunder.pyimagej_app_edit.setText(path)
            self.smlm_panel.thunder.status_label.setText("Fiji app path updated.")

    def _pick_smlm_fiji_executable(self) -> None:
        """Document the pick_smlm_fiji_executable flow."""
        if self.smlm_panel is None:
            return
        path, _ = QtWidgets.QFileDialog.getOpenFileName(self, "Select Fiji executable")
        if path:
            self.smlm_panel.thunder.fiji_exec_edit.setText(path)
            self.smlm_panel.thunder.status_label.setText("Fiji executable updated.")

    def _pick_smlm_plugin_jar(self) -> None:
        """Document the pick_smlm_plugin_jar flow."""
        if self.smlm_panel is None:
            return
        path, _ = QtWidgets.QFileDialog.getOpenFileName(self, "Select plugin JAR", "", "JAR Files (*.jar)")
        if path:
            self.smlm_panel.thunder.thunderstorm_jar_edit.setText(path)
            self.smlm_panel.thunder.status_label.setText("Plugin JAR updated.")

    def _list_smlm_plugin_commands(self) -> None:
        """Document the list_smlm_plugin_commands flow."""
        if self.smlm_panel is None:
            return
        jar = self.smlm_panel.thunder.thunderstorm_jar_edit.text().strip()
        if not jar:
            QtWidgets.QMessageBox.information(self, "Plugin Commands", "No plugin JAR selected.")
            return
        menus, commands = parse_plugins_config_from_jar(jar)
        if not commands:
            QtWidgets.QMessageBox.information(self, "Plugin Commands", "No commands discovered in plugins.config.")
            return
        lines = []
        for idx, command in enumerate(commands):
            menu = menus[idx] if idx < len(menus) else "(menu unknown)"
            lines.append(f"{idx + 1}. {command} [{menu}]")
        QtWidgets.QMessageBox.information(self, "Plugin Commands", "\n".join(lines))

    def _show_smlm_macro_viewer(self) -> None:
        """Document the show_smlm_macro_viewer flow."""
        if self.smlm_panel is None:
            return
        sw = self.smlm_panel.thunder
        sw.generated_macro_view.setVisible(True)
        sw.show_macro_btn.setText("Hide Generated Macro")

    def _open_smlm_logs_panel(self) -> None:
        """Document the open_smlm_logs_panel flow."""
        self.set_panel_visible("logs", True, source="smlm_fixit")

    def _open_smlm_error_folder(self) -> None:
        """Document the open_smlm_error_folder flow."""
        path = getattr(self, "_last_smlm_error_report_path", "")
        if path:
            folder = pathlib.Path(path).resolve().parent
        else:
            folder = pathlib.Path("artifacts") / "smlm_errors"
            folder.mkdir(parents=True, exist_ok=True)
        QtGui.QDesktopServices.openUrl(QtCore.QUrl.fromLocalFile(str(folder)))

    def _browse_deepstorm_model(self) -> None:
        """Document the browse_deepstorm_model flow."""
        if self.smlm_panel is None:
            return
        path, _ = QtWidgets.QFileDialog.getOpenFileName(
            self, "Select Deep-STORM model", "", "Model Files (*.pt)"
        )
        if path:
            self.smlm_panel.deep.model_path_edit.setText(path)

    def _deepstorm_params_from_ui(self) -> Optional[DeepStormParams]:
        """Document the deepstorm_params_from_ui flow."""
        if self.smlm_panel is None:
            return None
        values = self.smlm_panel.deep.values()
        return DeepStormParams(
            model_path=values.model_path,
            patch_size=values.patch_size,
            overlap=values.overlap,
            upsample=values.upsample,
            sigma_px=values.sigma_px,
            normalize_mode=values.normalize_mode,
            output_mode=values.output_mode,
            window_size=values.window_size,
            aggregation_mode=values.aggregation_mode,
        )

    def _deepstorm_to_annotations(self) -> None:
        """Document the deepstorm_to_annotations flow."""
        if not self._deepstorm_results:
            if self.smlm_panel is not None:
                self.smlm_panel.deep.status_label.setText("No Deep-STORM results to add.")
            return
        if hasattr(self, "_ensure_annotation_write_context_confirmed"):
            if not self._ensure_annotation_write_context_confirmed("Import Deep-STORM localizations"):
                return
        image_id = self.primary_image.id
        self._block_table = True
        for loc in self._deepstorm_results:
            self.controller.add_annotation(
                image_id=image_id,
                image_name=self.primary_image.name,
                t=-1,
                z=self.z_slider.value(),
                y=loc.y_px,
                x=loc.x_px,
                label=self.current_label,
                scope=self.annotation_scope,
            )
        self._block_table = False
        self._request_ui_refresh("smlm-controls", table=True)
        self._mark_dirty()
        if self.smlm_panel is not None:
            self.smlm_panel.deep.status_label.setText("Added to annotations.")

    def _torch_has_cuda(self) -> bool:
        """Document the torch_has_cuda flow."""
        try:
            import torch
        except Exception:
            return False
        return torch.cuda.is_available()

    def _validate_deepstorm_params(self, params: DeepStormParams) -> Tuple[Optional[str], Optional[str]]:
        """Document the validate_deepstorm_params flow."""
        if params.patch_size not in (64, 96, 128):
            return "Patch size must be 64/96/128.", None
        if params.overlap < 0 or params.overlap >= params.patch_size:
            return "Overlap must be smaller than patch size.", None
        if params.upsample < 2:
            return "Upsample must be >= 2.", None
        warn = None
        if not (1.0 <= params.sigma_px <= 1.8):
            warn = "Sigma outside recommended range (1.1–1.6 px)."
        return None, warn
