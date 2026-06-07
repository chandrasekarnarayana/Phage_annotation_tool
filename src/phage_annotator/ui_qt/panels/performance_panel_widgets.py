"""Extracted method group 2 for PerformancePanel."""

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



class PerformancePanelWidgetsMixin:
    """Method group 2 extracted from PerformancePanel."""

    def _create_memory_group(self) -> QtWidgets.QGroupBox:
        """Create system memory pressure group box (P3a)."""
        group = QtWidgets.QGroupBox("System Memory (P3a)")
        layout = QtWidgets.QGridLayout(group)

        # Available memory
        layout.addWidget(QtWidgets.QLabel("Available:"), 0, 0)
        self.memory_available_label = QtWidgets.QLabel("0 / 0 GB")
        self.memory_available_label.setStyleSheet("font-family: monospace;")
        layout.addWidget(self.memory_available_label, 0, 1)

        # Memory usage progress bar
        self.memory_progress = QtWidgets.QProgressBar()
        self.memory_progress.setRange(0, 100)
        self.memory_progress.setValue(0)
        layout.addWidget(self.memory_progress, 1, 0, 1, 2)

        # Pressure level
        layout.addWidget(QtWidgets.QLabel("Pressure:"), 2, 0)
        self.memory_pressure_label = QtWidgets.QLabel("LOW")
        self.memory_pressure_label.setStyleSheet("font-family: monospace; color: #51cf66;")
        layout.addWidget(self.memory_pressure_label, 2, 1)

        # Mitigation status (P3b)
        layout.addWidget(QtWidgets.QLabel("Mitigation:"), 3, 0)
        self.memory_mitigation_label = QtWidgets.QLabel("OFF")
        self.memory_mitigation_label.setStyleSheet("font-family: monospace;")
        layout.addWidget(self.memory_mitigation_label, 3, 1)

        return group
    def _setup_update_timer(self) -> None:
        """Set up the periodic update timer (500ms)."""
        self._update_timer = QtCore.QTimer(self)
        self._update_timer.timeout.connect(self._update_metrics)
        self._update_timer.setInterval(500)
    def set_cache(self, cache: Optional[ProjectionCache]) -> None:
        """Connect to projection cache."""
        self.cache = cache
    def set_ring_buffer(self, ring_buffer: Optional[FrameRingBuffer]) -> None:
        """Connect to ring buffer."""
        self.ring_buffer = ring_buffer
    def showEvent(self, event: QtGui.QShowEvent) -> None:
        """Start update timer when panel becomes visible."""
        super().showEvent(event)
        if self._update_timer:
            self._update_timer.start()
            self._update_metrics()
    def hideEvent(self, event: QtGui.QHideEvent) -> None:
        """Stop update timer when panel is hidden."""
        super().hideEvent(event)
        if self._update_timer:
            self._update_timer.stop()
    def _update_metrics(self) -> None:
        """Update all performance metrics from current state."""
        self._update_cache_metrics()
        self._update_jobs_metrics()
        self._update_buffer_metrics()
        self._update_pool_metrics()
        if HAS_PSUTIL:
            self._update_memory_metrics()  # P3a: System memory monitoring
        self._update_warnings()
    def _update_pool_metrics(self) -> None:
        """Update array pool telemetry metrics (P5)."""
        stats = ARRAY_POOL.stats()
        total = stats.hits + stats.misses
        hit_rate = (stats.hits / total) if total else 0.0
        self.pool_hits_label.setText(str(stats.hits))
        self.pool_misses_label.setText(str(stats.misses))
        self.pool_hit_rate_label.setText(f"{hit_rate * 100:.1f}%")
        self.pool_entries_label.setText(str(stats.entries))
        self.pool_drops_label.setText(str(stats.drops))
    def _update_cache_metrics(self) -> None:
        """Update cache statistics."""
        if not self.cache:
            return

        mb_used, item_count = self.cache.stats()
        mb_budget = int(self.cache._max_bytes / (1024 * 1024))
        telemetry = self.cache.telemetry()

        # Update labels
        self.cache_usage_label.setText(f"{mb_used} / {mb_budget} MB")
        self.cache_items_label.setText(str(item_count))
        self.cache_eviction_label.setText(str(telemetry.evictions))

        # Hit ratio
        hit_ratio = telemetry.hit_ratio()
        self.cache_hit_ratio_label.setText(f"{hit_ratio * 100:.1f}%")

        # Thrashing detection (P1a)
        is_thrashing = telemetry.is_thrashing()
        if is_thrashing:
            self.cache_thrashing_label.setText("YES")
            self.cache_thrashing_label.setStyleSheet("font-family: monospace; color: #ff6b6b; font-weight: bold;")
            logger.warning(f"Cache thrashing detected: {telemetry.evictions_this_cycle} evictions vs {telemetry.hits_this_cycle} hits")
        else:
            self.cache_thrashing_label.setText("NO")
            self.cache_thrashing_label.setStyleSheet("font-family: monospace;")

        # LOD mode indicator (P2a)
        if self.main_window and hasattr(self.main_window, '_lod_mode_active'):
            lod_active_count = sum(1 for v in self.main_window._lod_mode_active.values() if v)
            if lod_active_count > 0:
                self.cache_lod_mode_label.setText(f"ACTIVE ({lod_active_count})")
                self.cache_lod_mode_label.setStyleSheet("font-family: monospace; color: #4dabf7; font-weight: bold;")
            else:
                self.cache_lod_mode_label.setText("OFF")
                self.cache_lod_mode_label.setStyleSheet("font-family: monospace;")
        else:
            self.cache_lod_mode_label.setText("OFF")
            self.cache_lod_mode_label.setStyleSheet("font-family: monospace;")

        # Component memory tracking (P7e)
        try:
            main_bytes, main_mb = self.cache.get_component_usage('projection_main')
            pyr_bytes, pyr_mb = self.cache.get_component_usage('projection_pyramid')
            self.cache_component_main_label.setText(f"{main_mb} MB")
            self.cache_component_pyramid_label.setText(f"{pyr_mb} MB")
        except AttributeError:
            # Component tracking not available (older cache instance)
            pass

        # Progress bar
        percent = int((mb_used / mb_budget * 100)) if mb_budget > 0 else 0
        self.cache_progress.setValue(min(100, percent))
        self._cache_pressure_active = bool(percent >= 90)

        # Color code by usage
        if percent >= 90:
            self.cache_progress.setStyleSheet("QProgressBar::chunk { background-color: #ff6b6b; }")
        elif percent >= 75:
            self.cache_progress.setStyleSheet("QProgressBar::chunk { background-color: #ffa94d; }")
        else:
            self.cache_progress.setStyleSheet("QProgressBar::chunk { background-color: #51cf66; }")
        
        # Reset per-cycle counters for next monitoring tick
        telemetry.reset_cycle()
    def _update_jobs_metrics(self) -> None:
        """Update job queue and prefetch statistics."""
        if not self.main_window:
            return

        active_count = 0
        processed_count = 0
        pending_count = 0
        blocked_count = 0
        pending_capacity = 0
        queue_summary = "Idle"
        if hasattr(self.main_window, "jobs") and hasattr(self.main_window.jobs, "queue_snapshot"):
            telemetry = self.main_window.jobs.queue_snapshot()
            active_count = telemetry.active_count
            processed_count = telemetry.total_submitted
            pending_count = telemetry.pending_count
            blocked_count = telemetry.blocked_count
            pending_capacity = telemetry.max_pending_jobs
            if telemetry.pending:
                head = telemetry.pending[0]
                if head.state == "blocked" and head.blocked_by:
                    queue_summary = (
                        f"{head.name} waiting on {', '.join(head.blocked_by[:2])}"
                    )
                else:
                    queue_summary = f"{head.name} queued"
            elif telemetry.running:
                queue_summary = f"{telemetry.running[0].name} running"
            self.jobs_queue_list.clear()
            for job in telemetry.running:
                self.jobs_queue_list.addItem(f"RUN  {job.name}")
            for job in telemetry.pending:
                if job.blocked_by:
                    dep_text = ", ".join(job.blocked_by[:2])
                    self.jobs_queue_list.addItem(f"WAIT {job.name} <- {dep_text}")
                else:
                    self.jobs_queue_list.addItem(f"QUEUE {job.name}")
        else:
            self.jobs_queue_list.clear()

        self.jobs_active_label.setText(str(active_count))
        self.jobs_processed_label.setText(str(processed_count))
        self.jobs_pending_label.setText(f"{pending_count} / {pending_capacity}")
        self.jobs_blocked_label.setText(str(blocked_count))
        self.jobs_queue_summary_label.setText(queue_summary)
        self.jobs_cancel_queued_btn.setEnabled(pending_count > 0)
        self.jobs_cancel_blocked_btn.setEnabled(blocked_count > 0)

        # Prefetch queue depth (estimate from controller)
        prefetch_queue = 0
        if hasattr(self.main_window, "controller"):
            controller = self.main_window.controller
            if hasattr(controller, "_prefetch_queue"):
                prefetch_queue = len(controller._prefetch_queue)

        self.prefetch_queue_label.setText(str(prefetch_queue))
    def _update_buffer_metrics(self) -> None:
        """Update ring buffer statistics."""
        if not self.ring_buffer:
            return

        try:
            # Get buffer memory usage
            buffer_mb = 0
            if hasattr(self.ring_buffer, "_data"):
                data = self.ring_buffer._data
                if data is not None and isinstance(data, np.ndarray):
                    buffer_mb = int(np.ceil(data.nbytes / (1024 * 1024)))

            # Get buffer fill level
            fill_percent = 0
            frame_count = 0
            if hasattr(self.ring_buffer, "head") and hasattr(self.ring_buffer, "tail"):
                # Simple calculation based on head/tail pointers
                frame_count = self.ring_buffer.head - self.ring_buffer.tail

            self.buffer_memory_label.setText(f"{buffer_mb} MB")
            self.buffer_frames_label.setText(str(max(0, frame_count)))

            # Estimate fill level
            if hasattr(self.ring_buffer, "_capacity"):
                capacity = self.ring_buffer._capacity
                fill_percent = int((frame_count / capacity * 100)) if capacity > 0 else 0
            
            self.buffer_fill_label.setText(f"{min(100, fill_percent)}%")
        except Exception as e:
            logger.debug(f"Error updating buffer metrics: {e}")
