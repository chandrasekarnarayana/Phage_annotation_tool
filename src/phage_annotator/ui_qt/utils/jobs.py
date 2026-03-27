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
                priority="interactive",
                replace_key=str(name),
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
        try:
            # Brief status toast for user feedback
            self._status_info("Cancelling all jobs…", timeout_ms=3000, source="jobs.cancel_all")
            # Subtle audio + visual pulse to reinforce action
            try:
                from matplotlib.backends.qt_compat import QtWidgets  # already available
                QtWidgets.QApplication.beep()
            except Exception:
                pass
            try:
                if getattr(self, "progress_bar", None) is not None:
                    old_style = self.progress_bar.styleSheet()
                    pulse_style = (
                        "QProgressBar {border: 1px solid #f0ad4e; padding: 1px; border-radius: 3px;} "
                        "QProgressBar::chunk {background-color: #f0ad4e;}"
                    )
                    self.progress_bar.setStyleSheet(pulse_style)
                    # Restore after 500 ms
                    from matplotlib.backends.qt_compat import QtCore
                    QtCore.QTimer.singleShot(500, lambda: self.progress_bar.setStyleSheet(old_style))
            except Exception:
                pass
            self._append_log("[JOB] Cancel All requested")
        except Exception:
            # Best-effort logging; continue to cancel
            pass
        self.jobs.cancel_all()

    def _append_log(
        self,
        text: str,
        *,
        severity: str | None = None,
        category: str | None = None,
        details: str | None = None,
    ) -> None:
        entry = {
            "timestamp": datetime.now().strftime("%H:%M:%S"),
            "severity": self._infer_log_severity(text, severity=severity),
            "category": str(category or self._infer_log_category(text)),
            "summary": str(text).splitlines()[0] if str(text).splitlines() else str(text),
            "details": str(details if details is not None else text),
        }
        if hasattr(self, "_all_logs"):
            self._all_logs.append(entry)
        if hasattr(self, "_refresh_log_view"):
            try:
                self._refresh_log_view()
            except Exception:
                pass
        elif self.log_view is not None:
            self.log_view.appendPlainText(self._format_log_entry(entry))
        if hasattr(self, "_update_bottom_task_panels"):
            try:
                self._update_bottom_task_panels()
            except Exception:
                pass

    @staticmethod
    def _infer_log_severity(text: str, *, severity: str | None = None) -> str:
        if severity is not None:
            return str(severity).strip().upper()
        upper = str(text).upper()
        if "[EXCEPTION]" in upper or " ERROR" in upper or upper.startswith("[ERROR]") or "FAILED" in upper:
            return "ERROR"
        if "WARNING" in upper or upper.startswith("[WARN") or "CANCELLED" in upper:
            return "WARNING"
        if upper.startswith("[DEBUG]"):
            return "DEBUG"
        return "INFO"

    @staticmethod
    def _infer_log_category(text: str) -> str:
        raw = str(text).strip()
        if raw.startswith("[") and "]" in raw:
            return raw[1 : raw.index("]")].strip() or "General"
        return "General"

    @staticmethod
    def _format_log_entry(entry: dict[str, str]) -> str:
        prefix = f"[{entry.get('timestamp', '--:--:--')}] [{entry.get('severity', 'INFO')}]"
        category = entry.get("category")
        if category:
            prefix += f" [{category}]"
        return f"{prefix} {entry.get('summary', '')}".rstrip()

    def _install_exception_hook(self) -> None:
        """Install a global exception hook for GUI thread errors."""

        def _hook(exc_type, exc, tb):
            msg = "".join(traceback.format_exception(exc_type, exc, tb))
            LOGGER.error("Uncaught exception\n%s", msg, extra={"job_id": "gui"})
            self._append_log(
                f"[EXCEPTION] {exc_type.__name__}: {exc}",
                severity="ERROR",
                category="Exception",
                details=msg,
            )
            self._status_error(
                "Unexpected error. See Logs.",
                timeout_ms=7000,
                source="jobs.exception_hook",
            )
            auto_open_logs = bool(
                getattr(self, "_settings", None).value("autoOpenLogsOnError", False, type=bool)
                if getattr(self, "_settings", None) is not None
                else False
            )
            if auto_open_logs and self.dock_logs is not None:
                self.set_panel_visible("logs", True, source="auto:exception_hook")

        sys.excepthook = _hook

    def _on_job_started(self, name: str, job_id: str) -> None:
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
        self._append_log(f"[JOB] Finished: {name} ({job_id})", severity="INFO", category="Job")
        LOGGER.info("Job finished: %s", name, extra={"job_id": job_id})

    def _on_job_error(self, name: str, job_id: str, traceback_text: str) -> None:
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
        self._clear_projection_job_name(job_id)
        if self._active_job_id == job_id:
            if getattr(self, "status_service", None) is not None:
                self.status_service.clear_activity(str(job_id))
            else:
                self._set_progress_visible(False, "")
            self._active_job_id = None
            self._active_job_name = None

    def _set_progress_visible(self, visible: bool, name: str) -> None:
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
        if self._active_job_id is None:
            return
        self.jobs.cancel(self._active_job_id)

    def _cancel_projection_jobs(self, image_id: int) -> None:
        for kind in ("mean", "std"):
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
