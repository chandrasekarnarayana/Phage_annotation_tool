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


class JobManagementMixin:
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
            """Handle the do submit helper flow."""
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
        """Append log for the current workflow."""
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
        """Infer log severity for the current workflow."""
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
        """Infer log category for the current workflow."""
        raw = str(text).strip()
        if raw.startswith("[") and "]" in raw:
            return raw[1 : raw.index("]")].strip() or "General"
        return "General"

    @staticmethod
    def _format_log_entry(entry: dict[str, str]) -> str:
        """Format log entry for the current workflow."""
        prefix = f"[{entry.get('timestamp', '--:--:--')}] [{entry.get('severity', 'INFO')}]"
        category = entry.get("category")
        if category:
            prefix += f" [{category}]"
        return f"{prefix} {entry.get('summary', '')}".rstrip()

    def _install_exception_hook(self) -> None:
        """Install a global exception hook for GUI thread errors."""

        def _hook(exc_type, exc, tb):
            """Handle the hook helper flow."""
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
