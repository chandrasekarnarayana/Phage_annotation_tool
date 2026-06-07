"""Extracted method group 1 for RoiControlsMixin."""

from __future__ import annotations

import csv
import datetime as dt
import logging
import pathlib
import time
from typing import Optional

import numpy as np
from matplotlib.backends.qt_compat import QtCore, QtWidgets

from phage_annotator.roi.manager import Roi, save_rois_json, load_rois_json
from phage_annotator.roi.commands import (
    AddRoiCommand,
    DeleteRoiCommand,
    RenameRoiCommand,
    UpdateRoiGeometryCommand,
    BatchDeleteRoisCommand,
    AddTagCommand,
    RemoveTagCommand,
)
from phage_annotator.analysis.core import roi_mask_from_points, roi_mean_timeseries

logger = logging.getLogger(__name__)



class RoiManagerCoreMixin:
    """Method group 1 extracted from RoiControlsMixin."""

    def _roi_measurement_frame(self, arr: np.ndarray, t: int) -> np.ndarray:
        """Resolve a 2D measurement frame from T/Y/X or T/Z/Y/X image data."""
        frame = np.asarray(arr[t])
        if frame.ndim == 2:
            return frame
        if frame.ndim == 3:
            return np.asarray(frame[0])
        raise ValueError(f"Unsupported ROI measurement shape: {arr.shape}")
    def _roi_measurement_rows(self, arr: np.ndarray, rois: list[Roi], image_id: int) -> list[dict]:
        """Build deterministic ROI measurement rows with traceable ROI/image context."""
        results: list[dict] = []
        n_frames = int(arr.shape[0])
        image_shape = "x".join(str(int(v)) for v in np.shape(arr))
        for t in range(n_frames):
            try:
                frame = self._roi_measurement_frame(arr, t)
            except Exception as e:
                logger.warning(f"Failed to resolve ROI measurement frame at t={t}: {e}")
                continue

            for roi in rois:
                try:
                    mask = roi_mask_from_points(frame.shape, roi.roi_type, roi.points)
                    vals = frame[mask]

                    if vals.size == 0:
                        continue

                    y_idx, x_idx = np.where(mask)
                    results.append({
                        "Image_ID": int(image_id),
                        "Image_Shape": image_shape,
                        "Frame_T": int(t),
                        "ROI_ID": int(roi.roi_id),
                        "ROI_Name": roi.name,
                        "ROI_Type": roi.roi_type,
                        "ROI_Tags": ",".join(str(tag) for tag in getattr(roi, "tags", []) if str(tag).strip()),
                        "ROI_Z_Binding": int(getattr(roi, "z_index", -1)),
                        "ROI_T_Binding": int(getattr(roi, "t_index", -1)),
                        "ROI_C_Binding": int(getattr(roi, "c_index", -1)),
                        "Area_px2": float(mask.sum()),
                        "Mean_Intensity": float(vals.mean()),
                        "Min_Intensity": float(vals.min()),
                        "Max_Intensity": float(vals.max()),
                        "Centroid_X_px": float(x_idx.mean()) if len(x_idx) > 0 else 0.0,
                        "Centroid_Y_px": float(y_idx.mean()) if len(y_idx) > 0 else 0.0,
                        "Integral_Sum": float(vals.sum()),
                    })
                except Exception as e:
                    logger.warning(f"Failed to measure ROI {roi.name} at frame {t}: {e}")
                    continue
        results.sort(key=lambda row: (int(row["Frame_T"]), str(row["ROI_Name"]), int(row["ROI_ID"])))
        return results
    def _roi_measurement_summary_text(self, rows: list[dict], roi_count: int, frame_count: int, image_id: int) -> str:
        """Summarize ROI measurement scope and aggregate output for the dialog header."""
        if not rows:
            return f"Image {image_id} | {roi_count} ROI(s) | {frame_count} frame(s) | 0 measurement row(s)"
        mean_area = sum(float(row["Area_px2"]) for row in rows) / float(len(rows))
        mean_signal = sum(float(row["Mean_Intensity"]) for row in rows) / float(len(rows))
        return (
            f"Image {image_id} | {roi_count} ROI(s) | {frame_count} frame(s) | "
            f"{len(rows)} measurement row(s) | Mean area {mean_area:.1f} px^2 | "
            f"Mean signal {mean_signal:.3f}"
        )
    def _roi_measurement_default_path(self) -> pathlib.Path:
        """Return a traceable default CSV export path for ROI measurements."""
        image_id = int(getattr(getattr(self, "primary_image", None), "id", -1))
        stamp = dt.datetime.now().strftime("%Y%m%d")
        return pathlib.Path.cwd() / f"roi_measurements_image_{image_id}_{stamp}.csv"
    def _write_roi_measurements_csv(self, path: pathlib.Path, rows: list[dict]) -> None:
        """Write ROI measurements with stable metadata-rich columns."""
        with open(path, "w", newline="") as f:
            if rows:
                writer = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
                writer.writeheader()
                writer.writerows(rows)
    def _refresh_roi_manager(self) -> None:
        """Refresh roi manager for the current workflow."""
        if self.roi_manager_widget is None:
            return
        rois = self.roi_manager.list_rois(self.primary_image.id)
        self.roi_manager_widget.set_rois(rois)
        selected = self._roi_mgr_selected()
        self._sync_roi_inline_editor(selected)
    def _roi_current_points(self, roi_type: str) -> list[tuple[float, float]]:
        """Translate the current editor ROI rect into ROI points for persistence."""
        if self.roi_shape == "none" or self.roi_rect[2] <= 0 or self.roi_rect[3] <= 0:
            raise ValueError("Set an ROI first.")
        x, y, w, h = self.roi_rect
        kind = str(roi_type or "box").strip().lower()
        if kind == "circle":
            return [(x + w / 2, y + h / 2), (x + w / 2 + min(w, h) / 2, y + h / 2)]
        if kind == "polygon":
            return [(x, y), (x + w, y), (x + w, y + h), (x, y + h)]
        return [(x, y), (x + w, y + h)]
    def _sync_roi_inline_editor(self, roi: Optional[Roi]) -> None:
        """Keep inline ROI panel fields aligned with the current selection."""
        if getattr(self, "roi_measure_export_path_edit", None) is not None:
            try:
                if not self.roi_measure_export_path_edit.text().strip():
                    self.roi_measure_export_path_edit.setText(str(self._roi_measurement_default_path()))
            except Exception:
                pass
        if roi is None:
            if getattr(self, "roi_inline_name_edit", None) is not None and not self.roi_inline_name_edit.hasFocus():
                self.roi_inline_name_edit.setText("")
            if getattr(self, "roi_inline_tags_edit", None) is not None and not self.roi_inline_tags_edit.hasFocus():
                self.roi_inline_tags_edit.setText("")
            return
        if getattr(self, "roi_inline_name_edit", None) is not None and not self.roi_inline_name_edit.hasFocus():
            self.roi_inline_name_edit.setText(str(getattr(roi, "name", "")))
        if getattr(self, "roi_inline_type_combo", None) is not None and not self.roi_inline_type_combo.hasFocus():
            idx = self.roi_inline_type_combo.findText(str(getattr(roi, "roi_type", "box")))
            if idx >= 0:
                self.roi_inline_type_combo.setCurrentIndex(idx)
        if getattr(self, "roi_inline_tags_edit", None) is not None and not self.roi_inline_tags_edit.hasFocus():
            self.roi_inline_tags_edit.setText(", ".join(str(tag) for tag in getattr(roi, "tags", []) if str(tag).strip()))
    def _roi_mgr_add_inline(self) -> None:
        """Add a saved ROI using the inline panel fields instead of a popup dialog."""
        roi_name = str(
            getattr(self, "roi_inline_name_edit", None).text()
            if getattr(self, "roi_inline_name_edit", None) is not None
            else ""
        ).strip() or "ROI"
        roi_type = str(
            getattr(self, "roi_inline_type_combo", None).currentText()
            if getattr(self, "roi_inline_type_combo", None) is not None
            else "box"
        ).strip().lower()
        try:
            points = self._roi_current_points(roi_type)
        except ValueError as exc:
            self._status_warning(str(exc), timeout_ms=2500, source="roi.add")
            return
        roi = Roi(
            roi_id=int(time.time() * 1000),
            name=roi_name,
            roi_type=roi_type,
            points=points,
        )
        cmd = AddRoiCommand(self.roi_manager, self.primary_image.id, roi)
        if self.roi_manager.execute_command(cmd):
            self.roi_manager.set_active(roi.roi_id)
            self._refresh_roi_manager()
            self._sync_active_roi(roi)
            self._status_success(
                f"Saved ROI '{roi_name}'.",
                timeout_ms=2500,
                source="roi.add",
            )
        else:
            self._status_error("Failed to add ROI.", timeout_ms=3500, source="roi.add")
    def _roi_mgr_rename_inline(self) -> None:
        """Rename the selected ROI from the inline panel field."""
        roi = self._roi_mgr_selected()
        if roi is None:
            self._status_info("Select an ROI to rename.", timeout_ms=2500, source="roi.rename")
            return
        new_name = str(
            getattr(self, "roi_inline_name_edit", None).text()
            if getattr(self, "roi_inline_name_edit", None) is not None
            else ""
        ).strip()
        if not new_name:
            self._status_warning("ROI name cannot be empty.", timeout_ms=2500, source="roi.rename")
            return
        if new_name == str(roi.name):
            return
        cmd = RenameRoiCommand(self.roi_manager, self.primary_image.id, roi.roi_id, new_name)
        if self.roi_manager.execute_command(cmd):
            self._refresh_roi_manager()
            self._status_success(
                f"Renamed ROI to '{new_name}'.",
                timeout_ms=2500,
                source="roi.rename",
            )
        else:
            self._status_error("Failed to rename ROI.", timeout_ms=3000, source="roi.rename")
    def _roi_mgr_apply_tags_inline(self) -> None:
        """Apply comma-separated tags from the inline panel to the selected ROI."""
        roi = self._roi_mgr_selected()
        if roi is None:
            self._status_info("Select an ROI to edit tags.", timeout_ms=2500, source="roi.tags")
            return
        raw = str(
            getattr(self, "roi_inline_tags_edit", None).text()
            if getattr(self, "roi_inline_tags_edit", None) is not None
            else ""
        )
        target_tags = [tag.strip() for tag in raw.split(",") if tag.strip()]
        current_tags = list(getattr(roi, "tags", []) or [])
        for tag in list(current_tags):
            if tag not in target_tags:
                cmd = RemoveTagCommand(self.roi_manager, self.primary_image.id, roi.roi_id, tag)
                self.roi_manager.execute_command(cmd)
        for tag in target_tags:
            if tag in current_tags:
                continue
            cmd = AddTagCommand(self.roi_manager, self.primary_image.id, roi.roi_id, tag)
            self.roi_manager.execute_command(cmd)
        self._refresh_roi_manager()
        self._status_success("Updated ROI tags.", timeout_ms=2500, source="roi.tags")
    def _roi_mgr_filter_by_tag_inline(self) -> None:
        """Filter the ROI list from the inline tag filter field."""
        if self.roi_manager_widget is None:
            return
        raw = str(
            getattr(self, "roi_inline_filter_edit", None).text()
            if getattr(self, "roi_inline_filter_edit", None) is not None
            else ""
        )
        tags = [tag.strip() for tag in raw.split(",") if tag.strip()]
        self.roi_manager_widget.set_tag_filter(tags)
        self._status_info(
            f"Showing ROIs with tags: {', '.join(tags) if tags else 'all'}.",
            timeout_ms=2500,
            source="roi.tags",
        )
    def _roi_mgr_clear_tag_filter_inline(self) -> None:
        """Clear any inline ROI tag filter and show the full list again."""
        if getattr(self, "roi_inline_filter_edit", None) is not None:
            self.roi_inline_filter_edit.clear()
        if self.roi_manager_widget is not None:
            self.roi_manager_widget.set_tag_filter([])
        self._status_info("Showing all ROIs.", timeout_ms=2000, source="roi.tags")
