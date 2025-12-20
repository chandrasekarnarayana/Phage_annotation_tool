"""Background job wiring for the GUI."""

from __future__ import annotations

import sys
import time
import traceback

from matplotlib.backends.qt_compat import QtCore

from phage_annotator.jobs import CancelToken
from phage_annotator.logger import get_logger

LOGGER = get_logger(__name__)


class JobsMixin:
    """Mixin for JobManager integration and log handling."""

    def _bind_job_signals(self) -> None:
        """Connect JobManager signals to UI-thread handlers."""
        self.jobs.job_started.connect(self._on_job_started)
        self.jobs.job_progress.connect(self._on_job_progress)
        self.jobs.job_result.connect(self._on_job_result)
        self.jobs.job_error.connect(self._on_job_error)
        self.jobs.job_cancelled.connect(self._on_job_cancelled)
        self.jobs.job_finished.connect(self._on_job_finished)

    def _submit_analysis_job(
        self,
        fn,
        *,
        name: str,
        on_result=None,
        on_error=None,
        on_progress=None,
    ) -> CancelToken:
        """Submit an analysis job with optional throttling during playback."""
        token = CancelToken()
        throttle_hz = float(self._settings.value("throttleAnalysisHzDuringPlayback", 2, type=float))
        min_interval = 1.0 / throttle_hz if throttle_hz > 0 else 0.0

        def _do_submit() -> None:
            self._analysis_submit_pending = False
            self._analysis_last_submit = time.monotonic()
            self.jobs.submit(
                fn,
                name=name,
                on_result=on_result,
                on_error=on_error,
                on_progress=on_progress,
                cancel_token=token,
            )

        if self._playback_mode and min_interval > 0:
            now = time.monotonic()
            remaining = min_interval - (now - self._analysis_last_submit)
            if remaining > 0:
                if not self._analysis_submit_pending:
                    self._analysis_submit_pending = True
                    QtCore.QTimer.singleShot(int(remaining * 1000), _do_submit)
                return token

        _do_submit()
        return token

    def _bump_job_generation(self) -> None:
        """Invalidate cached job results by bumping a generation counter."""
        self._job_generation += 1
        self._projection_jobs.clear()
        self._pyramid_jobs.clear()
        self.proj_cache.clear()

    def _cancel_all_jobs(self) -> None:
        """Cancel all known background jobs."""
        self.jobs.cancel_all()

    def _append_log(self, text: str) -> None:
        if self.log_view is None:
            return
        self.log_view.appendPlainText(text)

    def _install_exception_hook(self) -> None:
        """Install a global exception hook for GUI thread errors."""

        def _hook(exc_type, exc, tb):
            msg = "".join(traceback.format_exception(exc_type, exc, tb))
            LOGGER.error("Uncaught exception\n%s", msg, extra={"job_id": "gui"})
            self._append_log(f"[EXCEPTION] {exc_type.__name__}: {exc}\n{msg}")
            self._set_status("Unexpected error. See Logs.")
            if self.dock_logs is not None:
                self.dock_logs.setVisible(True)

        sys.excepthook = _hook

    def _on_job_started(self, name: str, job_id: str) -> None:
        self._active_job_id = job_id
        self._active_job_name = name
        self._set_progress_visible(True, name)
        self._append_log(f"[JOB] Started: {name} ({job_id})")
        LOGGER.info("Job started: %s", name, extra={"job_id": job_id})

    def _on_job_progress(self, name: str, job_id: str, value: int, message: str) -> None:
        if self._active_job_id == job_id:
            if self.progress_bar is not None:
                self.progress_bar.setValue(value)
            if message:
                self._set_status(f"{name}: {message}")

    def _on_job_result(self, name: str, job_id: str, result: object) -> None:
        self._append_log(f"[JOB] Finished: {name} ({job_id})")
        LOGGER.info("Job finished: %s", name, extra={"job_id": job_id})

    def _on_job_error(self, name: str, job_id: str, traceback_text: str) -> None:
        self._append_log(f"[JOB] Error: {name} ({job_id})\n{traceback_text}")
        LOGGER.error("Job error: %s\n%s", name, traceback_text, extra={"job_id": job_id})
        self._set_status(f"Job error: {name}")
        if self.dock_logs is not None:
            self.dock_logs.setVisible(True)

    def _on_job_cancelled(self, name: str, job_id: str) -> None:
        self._append_log(f"[JOB] Cancelled: {name} ({job_id})")
        LOGGER.info("Job cancelled: %s", name, extra={"job_id": job_id})
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
        self._clear_projection_job_name(job_id)
        if self._active_job_id == job_id:
            self._set_progress_visible(False, "")
            self._active_job_id = None
            self._active_job_name = None

    def _set_progress_visible(self, visible: bool, name: str) -> None:
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
        if visible:
            self.progress_bar.setValue(0)

    def _cancel_active_job(self) -> None:
        if self._active_job_id is None:
            return
        self.jobs.cancel(self._active_job_id)

    def _cancel_projection_jobs(self, image_id: int) -> None:
        for kind in ("mean", "std", "composite"):
            keys = [k for k in self._projection_jobs.keys() if k[0] == image_id and k[1] == kind]
            for key in keys:
                job_id = self._projection_jobs.pop(key, None)
                if job_id:
                    self.jobs.cancel(job_id)

    def _clear_projection_job_name(self, job_id: str) -> None:
        for key, name in list(self._projection_jobs.items()):
            if name == job_id:
                self._projection_jobs.pop(key, None)

    def _run_demo_job(self) -> None:
        def _job(progress, cancel_token):
            import time

            for i in range(101):
                if cancel_token.is_cancelled():
                    return None
                progress(i, f"Step {i}/100")
                time.sleep(0.02)
            return None

        self.jobs.submit(_job, name="Demo Job")
