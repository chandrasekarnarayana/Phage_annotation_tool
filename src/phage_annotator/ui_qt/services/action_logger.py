"""Unified UI action logging for both file storage and real-time GUI display.

This module provides a SINGLE logging system that handles:
- File-based persistence (phage_annotator_actions.jsonl)
- Real-time GUI display (MainWindow._all_logs)
- Non-blocking async I/O
- Complete action tracking with timing and errors
"""

from __future__ import annotations

import json
import logging
import time
import traceback
from contextlib import contextmanager
from pathlib import Path
from threading import Thread
from typing import Any, Dict, Optional
from queue import Queue

from phage_annotator.utils.logger import get_logger

LOGGER = get_logger(__name__)


class ActionLogger:
    """Unified action logger - handles BOTH file and GUI logging."""

    # Class-level GUI owner reference (set by MainWindow at startup)
    _gui_owner: Optional[Any] = None

    def __init__(self, log_file: Optional[Path] = None):
        """Initialize action logger with optional file output.

        Parameters
        ----------
        log_file : Path, optional
            Path to write action log (JSON lines format).
        """
        self.log_file = log_file or Path.cwd() / "docs" / "reports" / "phage_annotator_actions.jsonl"
        self.log_file.parent.mkdir(parents=True, exist_ok=True)
        self.queue: Queue[Dict[str, Any]] = Queue(maxsize=10000)
        self.running = False
        self.writer_thread: Optional[Thread] = None
        self._start_writer()

    @classmethod
    def set_gui_owner(cls, owner: Optional[Any]) -> None:
        """Set the global GUI owner for real-time log display.
        
        Called once from MainWindow.__init__() to enable unified logging.
        
        Parameters
        ----------
        owner : MainWindow or None
            The main window instance (has _append_log method)
        """
        cls._gui_owner = owner

    def _start_writer(self) -> None:
        """Start background thread for writing logs."""
        if self.running:
            return
        self.running = True
        self.writer_thread = Thread(target=self._write_loop, daemon=True)
        self.writer_thread.start()

    def _write_loop(self) -> None:
        """Background loop for writing queued actions to disk."""
        try:
            with open(self.log_file, "a", encoding="utf-8", buffering=1) as f:
                while self.running:
                    try:
                        action = self.queue.get(timeout=1.0)
                        if action is None:  # Sentinel to stop
                            break
                        json_line = json.dumps(action, default=str)
                        f.write(json_line + "\n")
                        f.flush()
                    except Exception:
                        pass  # Queue timeout, continue
        except Exception as exc:
            LOGGER.error("Action logger write loop failed: %s", exc)

    def log_action(
        self,
        action: str,
        panel: str = "",
        details: Optional[Dict[str, Any]] = None,
        duration_ms: Optional[float] = None,
        error: Optional[str] = None,
    ) -> None:
        """Log a UI action to BOTH file and GUI in a unified operation.

        Parameters
        ----------
        action : str
            Action name (e.g., 'add_annotation', 'pixel_size_change')
        panel : str
            Panel name (annotate, prepare, qc, assist, table, etc.)
        details : dict, optional
            Action-specific parameters
        duration_ms : float, optional
            Duration of action in milliseconds
        error : str, optional
            Error message if action failed
        
        Note: This method automatically handles both:
        1. File persistence (phage_annotator_actions.jsonl async)
        2. GUI display (MainWindow._all_logs real-time)
        """
        # Record for file storage
        record = {
            "timestamp": time.time(),
            "action": str(action).strip(),
            "panel": str(panel).strip(),
            "details": dict(details or {}),
            "duration_ms": float(duration_ms) if duration_ms else None,
            "error": str(error).strip() if error else None,
        }
        
        # Queue to file (async, non-blocking)
        try:
            self.queue.put_nowait(record)
        except Exception:
            LOGGER.debug("Action log queue full, dropping oldest")
        
        # Push to GUI in real-time if owner is available
        if ActionLogger._gui_owner is not None:
            self._push_to_gui(action, panel, details)

    def _push_to_gui(
        self, 
        action: str, 
        panel: str, 
        details: Optional[Dict[str, Any]]
    ) -> None:
        """Push formatted action to GUI logs via _append_log().
        
        This is called automatically from log_action() when GUI owner is set.
        """
        try:
            # Format summary for GUI display
            detail_items = " | ".join(
                f"{k}={v}" for k, v in (details or {}).items()
            ) if details else ""
            summary = f"[{panel.upper()}] {action}"
            if detail_items:
                # Truncate details for readability (100 char limit)
                summary = f"{summary} | {detail_items[:100]}"
            
            # Call _append_log on the GUI owner
            owner = ActionLogger._gui_owner
            if hasattr(owner, "_append_log"):
                owner._append_log(summary, severity="INFO", category="Action")
        except Exception:
            # Silently fail - don't let GUI logging break file logging
            pass

    def log_click(self, button: str, panel: str = "") -> None:
        """Log a button click."""
        self.log_action("click", panel=panel, details={"button": button})

    def log_value_change(
        self,
        control: str,
        old_value: Any,
        new_value: Any,
        panel: str = "",
    ) -> None:
        """Log a control value change."""
        self.log_action(
            "value_changed",
            panel=panel,
            details={
                "control": control,
                "old_value": str(old_value),
                "new_value": str(new_value),
            },
        )

    def log_background_job(
        self,
        job_name: str,
        status: str = "started",
        duration_ms: Optional[float] = None,
        error: Optional[str] = None,
    ) -> None:
        """Log background job activity.

        Parameters
        ----------
        job_name : str
            Job name
        status : str
            'started', 'completed', 'cancelled', 'error'
        duration_ms : float, optional
            Job duration
        error : str, optional
            Error if job failed
        """
        self.log_action(
            "background_job",
            details={"job": job_name, "status": status},
            duration_ms=duration_ms,
            error=error,
        )

    @contextmanager
    def track_action(
        self,
        action: str,
        panel: str = "",
        details: Optional[Dict[str, Any]] = None,
    ):
        """Context manager for automatic action timing and error capture.

        Parameters
        ----------
        action : str
            Action name
        panel : str
            Panel name
        details : dict, optional
            Initial details dict

        Yields
        ------
        dict
            Details dict to be updated with result info
        """
        start_time = time.time()
        result_details = dict(details or {})
        error_msg = None

        try:
            yield result_details
        except Exception as exc:
            error_msg = f"{type(exc).__name__}: {exc}"
            LOGGER.error(
                "Action '%s' failed: %s\n%s",
                action,
                error_msg,
                traceback.format_exc(),
            )
        finally:
            duration_ms = (time.time() - start_time) * 1000
            self.log_action(
                action,
                panel=panel,
                details=result_details,
                duration_ms=duration_ms,
                error=error_msg,
            )

    def flush(self) -> None:
        """Wait for all queued actions to be written."""
        while not self.queue.empty():
            time.sleep(0.01)

    def stop(self) -> None:
        """Stop the action logger."""
        self.running = False
        if self.writer_thread:
            self.queue.put(None)  # Sentinel
            self.writer_thread.join(timeout=2.0)


# Global instance
_action_logger: Optional[ActionLogger] = None


def get_action_logger() -> ActionLogger:
    """Get or create the global action logger instance."""
    global _action_logger
    if _action_logger is None:
        _action_logger = ActionLogger()
    return _action_logger


def init_action_logger(log_file: Optional[Path] = None) -> ActionLogger:
    """Initialize the global action logger."""
    global _action_logger
    _action_logger = ActionLogger(log_file=log_file)
    return _action_logger
