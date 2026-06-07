"""Background job wiring for the GUI."""

from __future__ import annotations

import sys
import time
import traceback
from datetime import datetime

from matplotlib.backends.qt_compat import QtCore

from phage_annotator.ui_qt.services.status import ActivityStatus, StatusMessage
from phage_annotator.ui_qt.services.jobs import CancelToken
from phage_annotator.utils.logger import get_logger

LOGGER = get_logger(__name__)


class JobLifecycleMixin:
    def _on_job_started(self, name: str, job_id: str) -> None:
        """Handle the on job started helper flow."""
        self._active_job_id = job_id
        self._active_job_name = name
        if getattr(self, "status_service", None) is not None:
            self.status_service.set_activity(
                ActivityStatus(
                    activity_id=str(job_id),
                    text=str(name),
                    progress=0,
                    cancellable=True,
                    state="running",
                    source="jobs",
                )
            )
        else:
            self._set_progress_visible(True, name)
        self._append_log(f"[JOB] Started: {name} ({job_id})", severity="INFO", category="Job")
        LOGGER.info("Job started: %s", name, extra={"job_id": job_id})

    def _on_job_progress(self, name: str, job_id: str, value: int, message: str) -> None:
        """Handle the on job progress helper flow."""
        if self._active_job_id == job_id:
            if getattr(self, "status_service", None) is not None:
                activity_text = f"{name}: {message}" if message else str(name)
                self.status_service.update_activity(
                    activity_id=str(job_id),
                    text=activity_text,
                    progress=int(value),
                )
            else:
                if self.progress_bar is not None:
                    self.progress_bar.setValue(value)
                if message:
                    self._status_info(
                        f"{name}: {message}",
                        timeout_ms=2000,
                        source="jobs.progress",
                    )

    def _on_job_result(self, name: str, job_id: str, result: object) -> None:
        """Handle the on job result helper flow."""
        self._append_log(f"[JOB] Finished: {name} ({job_id})", severity="INFO", category="Job")
        LOGGER.info("Job finished: %s", name, extra={"job_id": job_id})

    def _on_job_error(self, name: str, job_id: str, traceback_text: str) -> None:
        """Handle the on job error helper flow."""
        self._append_log(
            f"[JOB] Error: {name} ({job_id})",
            severity="ERROR",
            category="Job",
            details=traceback_text,
        )
        LOGGER.error("Job error: %s\n%s", name, traceback_text, extra={"job_id": job_id})
        if getattr(self, "status_service", None) is not None:
            self.status_service.clear_activity(str(job_id))
            self.status_service.post_message(
                StatusMessage(
                    text=f"Job error: {name}",
                    severity="error",
                    timeout_ms=7000,
                    source="jobs",
                    sticky=False,
                )
            )
        else:
            self._status_error(
                f"Job error: {name}",
                timeout_ms=7000,
                source="jobs.error",
            )
        auto_open_logs = bool(
            getattr(self, "_settings", None).value("autoOpenLogsOnError", False, type=bool)
            if getattr(self, "_settings", None) is not None
            else False
        )
        if auto_open_logs and self.dock_logs is not None:
            self.set_panel_visible("logs", True, source="auto:job_error")

    def _on_job_cancelled(self, name: str, job_id: str) -> None:
        """Handle the on job cancelled helper flow."""
        self._append_log(f"[JOB] Cancelled: {name} ({job_id})", severity="WARNING", category="Job")
        LOGGER.info("Job cancelled: %s", name, extra={"job_id": job_id})
        if getattr(self, "status_service", None) is not None:
            self.status_service.clear_activity(str(job_id))
        self._clear_projection_job_name(job_id)
        if getattr(self, "_smlm_job_id", None) == job_id:
            self._smlm_job_id = None
            if getattr(self, "smlm_panel", None) is not None:
                self.smlm_panel.thunder.status_label.setText("Cancelled.")
                self.smlm_panel.thunder.run_btn.setEnabled(True)
                self.smlm_panel.thunder.cancel_btn.setEnabled(False)
        if getattr(self, "_deepstorm_job_id", None) == job_id:
            self._deepstorm_job_id = None
            if getattr(self, "smlm_panel", None) is not None:
                self.smlm_panel.deep.status_label.setText("Cancelled.")
                self.smlm_panel.deep.run_btn.setEnabled(True)
                self.smlm_panel.deep.cancel_btn.setEnabled(False)

    def _on_job_finished(self, name: str, job_id: str) -> None:
        """Handle the on job finished helper flow."""
        self._clear_projection_job_name(job_id)
        if self._active_job_id == job_id:
            if getattr(self, "status_service", None) is not None:
                self.status_service.clear_activity(str(job_id))
            else:
                self._set_progress_visible(False, "")
            self._active_job_id = None
            self._active_job_name = None

    def _set_progress_visible(self, visible: bool, name: str) -> None:
        """Set progress visible for the current workflow."""
        status_service = getattr(self, "status_service", None)
        if status_service is not None:
            if visible:
                status_service.set_activity(
                    ActivityStatus(
                        activity_id=str(getattr(self, "_active_job_id", "legacy-progress")),
                        text=str(name),
                        progress=0,
                        cancellable=True,
                        state="running",
                        source="jobs-legacy",
                    )
                )
            else:
                status_service.clear_activity(str(getattr(self, "_active_job_id", "legacy-progress")))
            return
        if (
            self.progress_label is None
            or self.progress_bar is None
            or self.progress_cancel_btn is None
        ):
            return
        self.progress_label.setText(f"Working: {name}")
        self.progress_label.setVisible(visible)
        self.progress_bar.setVisible(visible)
        self.progress_cancel_btn.setVisible(visible)
        # Show/hide and enable/disable the "Cancel All" button alongside progress widgets (P5.4)
        if hasattr(self, "progress_cancel_all_btn") and self.progress_cancel_all_btn is not None:
            self.progress_cancel_all_btn.setVisible(visible)
            if visible:
                try:
                    queue = self.jobs.queue_snapshot()
                    count = int(queue.active_count + queue.pending_count)
                except Exception:
                    count = 1
                self.progress_cancel_all_btn.setEnabled(count > 1)
                btn_text = f"Cancel All ({count})" if count > 1 else "Cancel All"
                self.progress_cancel_all_btn.setText(btn_text)
                tip_suffix = f" - {count} running/queued jobs" if count > 1 else ""
                self.progress_cancel_all_btn.setToolTip("Cancel all running and queued background jobs" + tip_suffix)
            else:
                self.progress_cancel_all_btn.setEnabled(False)
                self.progress_cancel_all_btn.setText("Cancel All")
        if visible:
            self.progress_bar.setValue(0)

    def _cancel_active_job(self) -> None:
        """Handle the cancel active job helper flow."""
        if self._active_job_id is None:
            return
        self.jobs.cancel(self._active_job_id)

    def _cancel_projection_jobs(self, image_id: int) -> None:
        """Handle the cancel projection jobs helper flow."""
        for kind in ("mean", "std"):
            keys = [k for k in self._projection_jobs.keys() if k[0] == image_id and k[1] == kind]
            for key in keys:
                job_id = self._projection_jobs.pop(key, None)
                if job_id:
                    self.jobs.cancel(job_id)

    def _clear_projection_job_name(self, job_id: str) -> None:
        """Clear projection job name for the current workflow."""
        for key, name in list(self._projection_jobs.items()):
            if name == job_id:
                self._projection_jobs.pop(key, None)

    def _run_demo_job(self) -> None:
        """Run demo job for the current workflow."""
        def _job(progress, cancel_token):
            """Handle the job helper flow."""
            import time

            for i in range(101):
                if cancel_token.is_cancelled():
                    return None
                progress(i, f"Step {i}/100")
                time.sleep(0.02)
            return None

        self.jobs.submit(_job, name="Demo Job")
