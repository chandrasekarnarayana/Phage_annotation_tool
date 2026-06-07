"""Extracted method group 2 for ExportMixin."""

from __future__ import annotations

import base64
import pathlib
import re
from datetime import datetime
from typing import Tuple

import numpy as np
from matplotlib.backends.qt_compat import QtWidgets

from phage_annotator.analysis.core import compute_projection
from phage_annotator.core.workspace_snapshot import (
    build_workspace_snapshot,
    extract_ui_workspace_state,
    workspace_layer_registry,
)
from phage_annotator.io.metadata.annotation import format_tokens
from phage_annotator.data.display_mapping import build_norm
from phage_annotator.ui_qt.rendering.export_view import (
    ExportOptions, render_view_to_array, render_layer_to_array,
    render_chunk_to_array, calculate_export_chunks, create_streaming_writer
)
from phage_annotator.ui_qt.utils.image_io import read_metadata
from phage_annotator.ui_qt.rendering.lut_manager import cmap_for
from phage_annotator.rendering.scalebar import ScaleBarSpec




class RoiSerializationMixin:
    """Method group 2 extracted from ExportMixin."""

    def _restore_ui_workspace_state(self, ui_state: dict) -> None:
        """Restore UI-level workspace state captured in project snapshot."""
        if not isinstance(ui_state, dict) or not ui_state:
            return

        panel_visibility = ui_state.get("panel_visibility")
        if isinstance(panel_visibility, dict):
            self._panel_visibility.update({str(k): bool(v) for k, v in panel_visibility.items()})

        point_visibility = ui_state.get("annotation_panel_visibility")
        if isinstance(point_visibility, dict):
            self._annotation_panel_visibility = {
                str(k): bool(v) for k, v in point_visibility.items()
            }

        self._canvas_layout_rows = int(ui_state.get("canvas_layout_rows", self._canvas_layout_rows))
        self._canvas_layout_cols = int(ui_state.get("canvas_layout_cols", self._canvas_layout_cols))
        self._active_layout_preset = str(
            ui_state.get("active_layout_preset", getattr(self, "_active_layout_preset", "Default"))
        )

        if bool(ui_state.get("sidebar_collapsed", False)) and hasattr(self, "_collapse_sidebar"):
            self._collapse_sidebar()
        elif hasattr(self, "_expand_sidebar"):
            self._expand_sidebar()

        if bool(ui_state.get("right_sidebar_collapsed", False)) and hasattr(self, "_collapse_right_sidebar"):
            self._collapse_right_sidebar()
        elif hasattr(self, "_expand_right_sidebar"):
            self._expand_right_sidebar()

        stack_idx = int(ui_state.get("sidebar_index", 0) or 0)
        if getattr(self, "sidebar_stack", None) is not None:
            stack_idx = max(0, min(stack_idx, max(0, self.sidebar_stack.count() - 1)))
            self.sidebar_stack.setCurrentIndex(stack_idx)

        linked_zoom_bounds = ui_state.get("linked_zoom_bounds")
        if isinstance(linked_zoom_bounds, dict):
            try:
                xlim = tuple(float(v) for v in linked_zoom_bounds.get("xlim", ()))
                ylim = tuple(float(v) for v in linked_zoom_bounds.get("ylim", ()))
                if len(xlim) == 2 and len(ylim) == 2:
                    self._last_zoom_linked = (xlim, ylim)
            except Exception:
                pass

        if hasattr(self, "_rebuild_canvas_for_layout"):
            self._rebuild_canvas_for_layout()
        if hasattr(self, "_refresh_panel_policy_controls"):
            self._refresh_panel_policy_controls()
        if hasattr(self, "_sync_panel_visibility_state"):
            self._sync_panel_visibility_state()

        # Geometry/state restore is optional best-effort and may be skipped in edge cases.
        geometry_bytes = self._decode_qbytearray(ui_state.get("window_geometry_b64"))
        state_bytes = self._decode_qbytearray(ui_state.get("window_state_b64"))
        if geometry_bytes:
            try:
                self.restoreGeometry(geometry_bytes)
            except Exception:
                pass
        if state_bytes:
            try:
                self.restoreState(state_bytes)
            except Exception:
                pass
    def _save_csv(self) -> None:
        """Save csv for the current workflow."""
        csv_path, _ = self._default_export_paths()
        self.controller.save_csv(self, csv_path)
        self._status_success(f"Saved CSV to {csv_path}", source="export.save_csv")
        self._mark_dirty(False)
    def _quick_save_csv(self) -> None:
        """Quick-save annotations CSV to the default path."""
        csv_path, _ = self._default_export_paths()
        self.controller.save_csv(self, csv_path)
        self._status_success(f"Saved CSV to {csv_path}", source="export.quick_save_csv")
        self._mark_dirty(False)
    def _save_json(self) -> None:
        """Save json for the current workflow."""
        _, json_path = self._default_export_paths()
        self.controller.save_json(self, json_path)
        self._status_success(f"Saved JSON to {json_path}", source="export.save_json")
        self._mark_dirty(False)
    def _default_export_paths(self) -> Tuple[pathlib.Path, pathlib.Path]:
        """Handle the default export paths helper flow."""
        context = (
            dict(self.controller.current_annotation_context() or {})
            if hasattr(self.controller, "current_annotation_context")
            else {}
        )
        panel_key = str(context.get("panel_key", getattr(self, "annotate_target", "frame")) or "frame")
        binding = (
            self.controller.annotation_binding_for_panel(panel_key)
            if hasattr(self.controller, "annotation_binding_for_panel")
            else {}
        )
        if binding.get("path"):
            bound_path = pathlib.Path(str(binding["path"]))
            csv_path = bound_path if bound_path.suffix.lower() == ".csv" else bound_path.with_suffix(".csv")
            json_path = bound_path if bound_path.suffix.lower() == ".json" else bound_path.with_suffix(".json")
            return csv_path, json_path
        source_image_id = int(context.get("source_image_id", getattr(self.primary_image, "id", 0)))
        source_image = next(
            (
                img for img in getattr(self, "images", [])
                if int(getattr(img, "id", -1)) == source_image_id
            ),
            self.primary_image,
        )
        first = source_image.path
        csv_path = pathlib.Path(first).with_suffix(".annotations.csv")
        json_path = pathlib.Path(first).with_suffix(".annotations.json")
        export_meta = self.controller.build_annotation_export_metadata(
            self.primary_image.id,
            export_format="bundle",
        )
        ts = datetime.now().strftime("%Y%m%dT%H%M%S")
        img_name = pathlib.Path(str(getattr(source_image, "name", "image"))).stem
        core_tokens = (
            f"__ann__img={self._tokenize_filename_value(img_name)}"
            f"__ts={ts}{self._annotation_filename_context_tokens()}"
        )
        csv_path = csv_path.with_name(f"{csv_path.stem}{core_tokens}{csv_path.suffix}")
        json_path = json_path.with_name(f"{json_path.stem}{core_tokens}{json_path.suffix}")
        if self._settings.value("encodeAnnotationMetaFilename", False, type=bool):
            meta = self.controller.build_annotation_metadata(self.primary_image.id)
            tokens = format_tokens(meta)
            if tokens:
                csv_path = csv_path.with_name(f"{csv_path.stem}{tokens}{csv_path.suffix}")
                json_path = json_path.with_name(f"{json_path.stem}{tokens}{json_path.suffix}")
        return csv_path, json_path
