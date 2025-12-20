"""Results table handlers."""

from __future__ import annotations

import pathlib
from typing import List

from matplotlib.backends.qt_compat import QtWidgets

from phage_annotator.analysis import roi_mask_from_points, roi_stats
from phage_annotator.roi_manager import Roi


class ResultsControlsMixin:
    """Mixin for results table handlers."""

    def _results_clear(self) -> None:
        if self.results_widget is not None:
            self.results_widget.clear()

    def _results_copy(self) -> None:
        if self.results_widget is not None:
            self.results_widget.copy_to_clipboard()

    def _results_export(self) -> None:
        if self.results_widget is None:
            return
        path, _ = QtWidgets.QFileDialog.getSaveFileName(
            self,
            "Export Results",
            str(pathlib.Path.cwd() / "results.csv"),
            "CSV Files (*.csv)",
        )
        if not path:
            return
        self.results_widget.export_csv(path)

    def _results_measure_current(self) -> None:
        if self.primary_image.array is None or self.results_widget is None:
            return
        rois = self._results_rois()
        if not rois:
            return
        t = self.t_slider.value()
        z = self.z_slider.value()
        frame = self.primary_image.array[t, z, :, :]
        for roi in rois:
            mask = roi_mask_from_points(frame.shape, roi.roi_type, roi.points)
            mean, std, vmin, vmax, area_px = roi_stats(frame, mask)
            cal = self._get_calibration_state(self.primary_image.id)
            px_um = cal.pixel_size_um_per_px
            area_um2 = area_px * (px_um**2) if px_um else None
            self.results_widget.add_row(
                {
                    "image_name": self.primary_image.name,
                    "t": t,
                    "z": z,
                    "roi_id": roi.roi_id,
                    "mean": f"{mean:.4f}",
                    "std": f"{std:.4f}",
                    "min": f"{vmin:.4f}",
                    "max": f"{vmax:.4f}",
                    "area_pixels": area_px,
                    "area_um2": f"{area_um2:.4f}" if area_um2 is not None else "",
                }
            )

    def _results_measure_over_time(self) -> None:
        if self.primary_image.array is None or self.results_widget is None:
            return
        rois = self._results_rois()
        if not rois:
            return
        arr = self.primary_image.array
        z = self.z_slider.value()
        job_gen = self._job_generation
        roi_defs = [(roi.roi_id, roi.roi_type, list(roi.points)) for roi in rois]
        img_name = self.primary_image.name
        cal = self._get_calibration_state(self.primary_image.id)
        pixel_size = cal.pixel_size_um_per_px or 0.0
        self._results_job_context = {
            "arr": arr,
            "z": z,
            "roi_defs": roi_defs,
            "img_name": img_name,
            "pixel_size": pixel_size,
            "job_gen": job_gen,
        }
        self.jobs.submit(
            self._results_job,
            name="ROI Measure T",
            on_progress=self._results_on_progress,
            on_result=self._results_on_result,
            on_error=self._results_on_error,
            timeout_sec=300.0,
            retries=1,
            retry_delay_sec=0.5,
        )

    def _results_job(self, progress, cancel_token) -> int | None:
        ctx = getattr(self, "_results_job_context", None)
        if ctx is None:
            return None
        arr = ctx["arr"]
        z = ctx["z"]
        roi_defs = ctx["roi_defs"]
        img_name = ctx["img_name"]
        pixel_size = ctx["pixel_size"]
        job_gen = ctx["job_gen"]

        total = arr.shape[0]
        masks = {}
        for roi_id, roi_type, points in roi_defs:
            masks[roi_id] = roi_mask_from_points(arr.shape[2:], roi_type, points)

        for t in range(total):
            if cancel_token.is_cancelled():
                return None
            frame = arr[t, z, :, :]
            for roi_id, _, _ in roi_defs:
                mean, std, vmin, vmax, area_px = roi_stats(frame, masks[roi_id])
                area_um2 = area_px * (pixel_size**2)
                payload = ",".join(
                    [
                        img_name,
                        str(t),
                        str(z),
                        str(roi_id),
                        f"{mean:.4f}",
                        f"{std:.4f}",
                        f"{vmin:.4f}",
                        f"{vmax:.4f}",
                        str(area_px),
                        f"{area_um2:.4f}",
                    ]
                )
                progress(int((t + 1) / total * 100), payload)
        return job_gen

    def _results_on_progress(self, value: int, msg: str) -> None:
        if self.results_widget is None:
            return
        parts = msg.split(",")
        if len(parts) != 10:
            return
        row = {
            "image_name": parts[0],
            "t": parts[1],
            "z": parts[2],
            "roi_id": parts[3],
            "mean": parts[4],
            "std": parts[5],
            "min": parts[6],
            "max": parts[7],
            "area_pixels": parts[8],
            "area_um2": parts[9],
        }
        self.results_widget.add_row(row)

    def _results_on_result(self, result: int | None) -> None:
        if result is None:
            return
        if result != self._job_generation:
            return

    def _results_on_error(self, err: str) -> None:
        self._append_log(f"[JOB] Results error\n{err}")

    def _results_rois(self) -> List[Roi]:
        active = self.roi_manager.get_active(self.primary_image.id)
        if active is not None:
            return [active]
        return self.roi_manager.list_rois(self.primary_image.id)
