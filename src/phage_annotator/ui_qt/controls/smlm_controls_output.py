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

class SmlmControlsOutputMixin:
    """CSV/HDF5 export and point layer toggling."""

    def _export_smlm_csv(self) -> None:
        """Document the export_smlm_csv flow."""
        if not self._smlm_results:
            if self.smlm_panel is not None:
                self.smlm_panel.thunder.status_label.setText("No SMLM results to export.")
            return
        settings = getattr(self, "_settings", None)
        default_dir = ""
        if settings is not None:
            default_dir = str(settings.value("smlmLastExportDir", "", type=str) or "")
        if not default_dir:
            default_dir = str(pathlib.Path.cwd())
        default_name = f"thunderstorm_results_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv"
        path, _ = QtWidgets.QFileDialog.getSaveFileName(
            self,
            "Export SMLM CSV",
            str(pathlib.Path(default_dir) / default_name),
            "CSV Files (*.csv)",
        )
        if not path:
            return
        if self.smlm_panel is not None:
            self.smlm_panel.thunder.export_localizations_csv(path)
        else:
            with open(path, "w", newline="") as f:
                writer = csv.writer(f)
                writer.writerow(
                    [
                        "frame_index",
                        "x_px",
                        "y_px",
                        "sigma_px",
                        "photons",
                        "background",
                        "uncertainty_px",
                        "label",
                    ]
                )
                for loc in self._smlm_results:
                    writer.writerow(
                        [
                            loc.frame_index,
                            f"{loc.x_px:.4f}",
                            f"{loc.y_px:.4f}",
                            f"{loc.sigma_px:.4f}",
                            f"{loc.photons:.4f}",
                            f"{loc.background:.4f}",
                            f"{loc.uncertainty_px:.4f}",
                            loc.label or "",
                        ]
                    )
        if settings is not None:
            settings.setValue("smlmLastExportDir", str(pathlib.Path(path).parent))
        if self.smlm_panel is not None:
            self.smlm_panel.thunder.status_label.setText(f"Exported CSV: {path}")

    def _export_smlm_hdf5(self) -> None:
        """Document the export_smlm_hdf5 flow."""
        if not self._smlm_results:
            if self.smlm_panel is not None:
                self.smlm_panel.thunder.status_label.setText("No SMLM results to export.")
            return
        try:
            import h5py
        except Exception:
            if self.smlm_panel is not None:
                self.smlm_panel.thunder.status_label.setText("h5py not available.")
            return
        path, _ = QtWidgets.QFileDialog.getSaveFileName(self, "Export SMLM HDF5", "", "HDF5 Files (*.h5)")
        if not path:
            return
        data = np.zeros(
            (len(self._smlm_results),),
            dtype=[
                ("frame_index", "i4"),
                ("x_px", "f4"),
                ("y_px", "f4"),
                ("sigma_px", "f4"),
                ("photons", "f4"),
                ("background", "f4"),
                ("uncertainty_px", "f4"),
            ],
        )
        for i, loc in enumerate(self._smlm_results):
            data[i] = (loc.frame_index, loc.x_px, loc.y_px, loc.sigma_px, loc.photons, loc.background, loc.uncertainty_px)
        with h5py.File(path, "w") as f:
            f.create_dataset("localizations", data=data, compression="gzip")
        if self.smlm_panel is not None:
            self.smlm_panel.thunder.status_label.setText(f"Exported HDF5: {path}")

    def _smlm_to_annotations(self) -> None:
        """Document the smlm_to_annotations flow."""
        if not self._smlm_results:
            if self.smlm_panel is not None:
                self.smlm_panel.thunder.status_label.setText("No SMLM results to add.")
            return
        if hasattr(self, "_ensure_annotation_write_context_confirmed"):
            if not self._ensure_annotation_write_context_confirmed("Import SMLM localizations"):
                return
        image_id = self.primary_image.id
        locs_to_add = list(self._smlm_results)
        if self.smlm_panel is not None:
            selected = self.smlm_panel.thunder.selected_localizations()
            if selected:
                locs_to_add = selected
        self._block_table = True
        for loc in locs_to_add:
            self.controller.add_annotation(
                image_id=image_id,
                image_name=self.primary_image.name,
                t=loc.frame_index,
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
            self.smlm_panel.thunder.status_label.setText(
                f"Added {len(locs_to_add)} localization(s) to annotations."
            )

    def _toggle_smlm_points(self) -> None:
        """Document the toggle_smlm_points flow."""
        if getattr(self, "show_smlm_points_act", None) is not None:
            self.show_smlm_points = self.show_smlm_points_act.isChecked()
            if self.smlm_panel is not None and hasattr(self.smlm_panel.thunder, "show_points_chk"):
                self.smlm_panel.thunder.show_points_chk.blockSignals(True)
                self.smlm_panel.thunder.show_points_chk.setChecked(bool(self.show_smlm_points))
                self.smlm_panel.thunder.show_points_chk.blockSignals(False)
            self._request_ui_refresh("smlm-controls")

    def _toggle_smlm_sr(self) -> None:
        """Document the toggle_smlm_sr flow."""
        if getattr(self, "show_smlm_sr_act", None) is not None:
            self.show_sr_overlay = self.show_smlm_sr_act.isChecked()
            self._request_ui_refresh("smlm-controls")
