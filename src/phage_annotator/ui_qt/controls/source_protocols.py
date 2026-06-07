"""Extracted method group 4 for SmlmControlsMixin."""

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



class SourceProtocolsMixin:
    """Method group 4 extracted from SmlmControlsMixin."""

    def _export_smlm_csv(self) -> None:
        """Export smlm csv for the current workflow."""
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
        """Export smlm hdf5 for the current workflow."""
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
        """Handle the smlm to annotations helper flow."""
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
    def _browse_deepstorm_model(self) -> None:
        """Handle the browse deepstorm model helper flow."""
        if self.smlm_panel is None:
            return
        path, _ = QtWidgets.QFileDialog.getOpenFileName(
            self, "Select Deep-STORM model", "", "Model Files (*.pt)"
        )
        if path:
            self.smlm_panel.deep.model_path_edit.setText(path)
    def _deepstorm_params_from_ui(self) -> Optional[DeepStormParams]:
        """Handle the deepstorm params from ui helper flow."""
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
