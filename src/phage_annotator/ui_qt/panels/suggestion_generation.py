"""Extracted method group 3 for PerformancePanel."""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Optional

import numpy as np
from matplotlib.backends.qt_compat import QtCore, QtGui, QtWidgets

from phage_annotator.cache.array_pool import ARRAY_POOL

try:
    import psutil
    HAS_PSUTIL = True
except ImportError:
    HAS_PSUTIL = False

if TYPE_CHECKING:
    from phage_annotator.data.ring_buffer import FrameRingBuffer
    from phage_annotator.cache.projection_cache import ProjectionCache
    from phage_annotator.ui_qt.main_window import MainWindow

logger = logging.getLogger(__name__)


# Memory pressure thresholds (percentage of available RAM)
MEMORY_PRESSURE_HIGH_THRESHOLD = 0.20  # <20% available
MEMORY_PRESSURE_MEDIUM_THRESHOLD = 0.80  # Between 20% and 80% available
MEMORY_PRESSURE_LOW_THRESHOLD = 0.80  # >80% available



class SuggestionGenerationMixin:
    """Method group 3 extracted from PerformancePanel."""

    def _update_memory_metrics(self) -> None:
        """Update system memory pressure metrics (P3a).
        
        Monitors available system RAM and triggers mitigation if pressure exceeds threshold.
        """
        if not HAS_PSUTIL:
            return

        try:
            mem = psutil.virtual_memory()
            total_gb = mem.total / (1024**3)
            available_gb = mem.available / (1024**3)
            available_pct = mem.available / mem.total
            
            # Update UI labels
            self.memory_available_label.setText(f"{available_gb:.1f} / {total_gb:.1f} GB")
            
            # Calculate usage percentage (inverse of available)
            usage_pct = int((1 - available_pct) * 100)
            self.memory_progress.setValue(min(100, usage_pct))
            
            # Determine pressure level and update status display
            if available_pct < MEMORY_PRESSURE_HIGH_THRESHOLD:
                pressure = "HIGH"
                color = "#ff6b6b"  # Red
                self._memory_pressure_active = True
            elif available_pct < MEMORY_PRESSURE_MEDIUM_THRESHOLD:
                pressure = "MEDIUM"
                color = "#ffa94d"  # Orange
                self._memory_pressure_active = True
            else:
                pressure = "LOW"
                color = "#51cf66"  # Green
                self._memory_pressure_active = False
            
            self.memory_pressure_label.setText(pressure)
            self.memory_pressure_label.setStyleSheet(f"font-family: monospace; color: {color};")
            
            # Update progress bar color based on pressure
            if pressure == "HIGH":
                self.memory_progress.setStyleSheet("QProgressBar::chunk { background-color: #ff6b6b; }")
            elif pressure == "MEDIUM":
                self.memory_progress.setStyleSheet("QProgressBar::chunk { background-color: #ffa94d; }")
            else:
                self.memory_progress.setStyleSheet("QProgressBar::chunk { background-color: #51cf66; }")
            
            # P3a: Trigger mitigation if memory pressure detected
            if self._memory_pressure_active and self.main_window:
                self._trigger_memory_mitigation()
            
        except Exception as e:
            logger.debug(f"Error updating memory metrics: {e}")
    def _trigger_memory_mitigation(self) -> None:
        """Trigger memory pressure mitigation (P3a & P3b).
        
        Actions:
        1. Disable pyramid prefetch (reduce background jobs)
        2. Reduce inference tile size 512 → 256 → 128
        3. Clear non-active image caches
        4. Update UI status
        """
        if not self.main_window:
            return

        try:
            # Action 1: Disable prefetch if not already disabled (P3b)
            if not self._last_prefetch_disabled:
                # Set flag to disable new pyramid prefetch jobs
                if hasattr(self.main_window, '_prefetch_disabled'):
                    self.main_window._prefetch_disabled = True
                self._last_prefetch_disabled = True
                logger.warning("Memory pressure detected: Disabling pyramid prefetch")
            
            # Action 2: Adaptive tile sizing (P3b)
            if hasattr(self.main_window, '_adaptive_tile_size'):
                current_size = self.main_window._adaptive_tile_size
                if current_size == 512:
                    self.main_window._adaptive_tile_size = 256
                    logger.warning("Memory pressure: Reduced inference tile size to 256px")
                elif current_size == 256:
                    self.main_window._adaptive_tile_size = 128
                    logger.warning("Memory pressure: Critical - reduced inference tile size to 128px")
            
            # Action 3: Clear non-active image caches
            if hasattr(self.main_window, '_evict_image_cache'):
                for img in self.main_window.images:
                    if img.id not in (self.main_window.current_image_idx, 
                                     self.main_window.support_image_idx):
                        try:
                            self.main_window._evict_image_cache(img)
                        except Exception:
                            pass
            
            # Action 4: Update UI status
            self.memory_mitigation_label.setText("ACTIVE")
            self.memory_mitigation_label.setStyleSheet("font-family: monospace; color: #ff6b6b; font-weight: bold;")
            
        except Exception as e:
            logger.debug(f"Error triggering memory mitigation: {e}")
    def _update_warnings(self) -> None:
        """Update warning messages."""
        warnings = []

        # Cache warning
        if self.cache:
            mb_used, _ = self.cache.stats()
            mb_budget = int(self.cache._max_bytes / (1024 * 1024))
            percent = (mb_used / mb_budget * 100) if mb_budget > 0 else 0
            if percent >= 90:
                telemetry = self.cache.telemetry()
                warnings.append(
                    f"⚠ Cache at {percent:.0f}% of budget "
                    f"({mb_used}/{mb_budget} MB, evictions: {telemetry.evictions})"
                )

        # Jobs warning
        if self.main_window and hasattr(self.main_window, "jobs"):
            telemetry = None
            if hasattr(self.main_window.jobs, "queue_snapshot"):
                telemetry = self.main_window.jobs.queue_snapshot()
            active_count = int(getattr(telemetry, "active_count", 0))
            pending_count = int(getattr(telemetry, "pending_count", 0))
            pending_capacity = max(1, int(getattr(telemetry, "max_pending_jobs", 1)))
            if active_count >= 5:
                warnings.append(f"⚠ {active_count} jobs running (potential slowdown)")
            if pending_count >= pending_capacity:
                warnings.append(
                    f"⚠ Job queue saturated ({pending_count}/{pending_capacity}); "
                    "consider cancelling stale background work"
                )
            elif int(getattr(telemetry, "blocked_count", 0)) > 0:
                warnings.append(
                    f"⚠ {int(getattr(telemetry, 'blocked_count', 0))} queued jobs waiting on dependencies"
                )

        # Memory pressure warning (P3a)
        if HAS_PSUTIL and self._memory_pressure_active:
            try:
                mem = psutil.virtual_memory()
                available_pct = mem.available / mem.total * 100
                warnings.append(f"⚠ Memory pressure: only {available_pct:.0f}% available (mitigation active)")
            except Exception:
                pass

        # No warnings
        if not warnings:
            self.warnings_label.setText("None - Performance nominal")
            self.warnings_label.setStyleSheet("color: #51cf66; font-weight: normal;")
        else:
            self.warnings_label.setText("\n".join(warnings))
            self.warnings_label.setStyleSheet("color: #ff6b6b; font-weight: bold;")
    def _clear_projection_cache(self) -> None:
        """Clear projection cache and surface the action through existing UI feedback."""
        if not self.cache:
            return
        try:
            self.cache.clear()
            self.cache.telemetry().reset()
        except Exception as exc:
            logger.debug(f"Error clearing projection cache: {exc}")
            return
        self._cache_pressure_active = False
        self._update_metrics()
        if self.main_window is not None and hasattr(self.main_window, "_status_success"):
            try:
                self.main_window._status_success(
                    "Projection cache cleared.",
                    timeout_ms=3000,
                    source="performance.clear_cache",
                )
            except Exception:
                pass
    def reset_telemetry(self) -> None:
        """Reset cache telemetry counters."""
        if self.cache:
            self.cache.telemetry().reset()
            self._update_cache_metrics()
    def _cancel_queued_jobs(self) -> None:
        """Handle the cancel queued jobs helper flow."""
        if not self.main_window or not hasattr(self.main_window, "jobs"):
            return
        cancelled = self.main_window.jobs.cancel_matching(include_running=False)
        self._update_metrics()
        if cancelled and hasattr(self.main_window, "_status_info"):
            self.main_window._status_info(
                f"Cancelled {len(cancelled)} queued jobs.",
                timeout_ms=3000,
                source="performance.cancel_queued",
            )
    def _cancel_blocked_jobs(self) -> None:
        """Handle the cancel blocked jobs helper flow."""
        if not self.main_window or not hasattr(self.main_window, "jobs"):
            return
        telemetry = self.main_window.jobs.queue_snapshot()
        cancelled = []
        for job in telemetry.pending:
            if job.state != "blocked":
                continue
            if self.main_window.jobs.cancel(job.job_id):
                cancelled.append(job.job_id)
        self._update_metrics()
        if cancelled and hasattr(self.main_window, "_status_info"):
            self.main_window._status_info(
                f"Cancelled {len(cancelled)} dependency-blocked jobs.",
                timeout_ms=3000,
                source="performance.cancel_blocked",
            )
