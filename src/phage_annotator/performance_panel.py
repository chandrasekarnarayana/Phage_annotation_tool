"""Consolidated performance monitoring panel for cache, jobs, and buffers.

P5.1 Implementation: Real-time performance metrics dashboard showing:
  - Projection cache usage (MB / budget, hit ratio, eviction count)
  - Active job count and prefetch queue status
  - Ring buffer memory usage
  - Performance warnings (cache at 90% budget, jobs backing up)

The panel updates every 500ms when visible and integrates with the session
state, cache telemetry, job queue, and ring buffer management.
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Optional

import numpy as np
from matplotlib.backends.qt_compat import QtCore, QtGui, QtWidgets

if TYPE_CHECKING:
    from phage_annotator.gui_mpl import MainWindow
    from phage_annotator.projection_cache import ProjectionCache
    from phage_annotator.ring_buffer import RingBuffer

logger = logging.getLogger(__name__)


class PerformancePanel(QtWidgets.QWidget):
    """Real-time performance metrics panel for cache, jobs, and buffers.
    
    Displays:
    - Cache: Memory usage, hit ratio, eviction count
    - Jobs: Active count, prefetch queue depth
    - Buffers: Ring buffer memory usage
    - Warnings: 90% cache threshold, job queue saturation
    """

    def __init__(self, parent: Optional[MainWindow] = None) -> None:
        super().__init__(parent)
        self.main_window = parent
        self.cache: Optional[ProjectionCache] = None
        self.ring_buffer: Optional[RingBuffer] = None
        self._update_timer: Optional[QtCore.QTimer] = None
        
        self._init_ui()
        self._setup_update_timer()

    def _init_ui(self) -> None:
        """Initialize the performance panel UI."""
        layout = QtWidgets.QVBoxLayout(self)
        layout.setContentsMargins(4, 4, 4, 4)
        layout.setSpacing(8)

        # Cache section
        cache_group = self._create_cache_group()
        layout.addWidget(cache_group)

        # Jobs section
        jobs_group = self._create_jobs_group()
        layout.addWidget(jobs_group)

        # Ring buffer section
        buffer_group = self._create_buffer_group()
        layout.addWidget(buffer_group)

        # Warnings/alerts section
        self.warnings_label = QtWidgets.QLabel()
        self.warnings_label.setWordWrap(True)
        self.warnings_label.setStyleSheet("color: #ff6b6b; font-weight: bold;")
        layout.addWidget(QtWidgets.QLabel("Warnings:"))
        layout.addWidget(self.warnings_label)

        # Refresh button
        refresh_btn = QtWidgets.QPushButton("Force Refresh")
        refresh_btn.clicked.connect(self._update_metrics)
        layout.addWidget(refresh_btn)

        layout.addStretch()
        self.setLayout(layout)

    def _create_cache_group(self) -> QtWidgets.QGroupBox:
        """Create cache metrics group box."""
        group = QtWidgets.QGroupBox("Projection Cache")
        layout = QtWidgets.QGridLayout(group)

        # Cache usage bar
        layout.addWidget(QtWidgets.QLabel("Memory:"), 0, 0)
        self.cache_usage_label = QtWidgets.QLabel("0 / 1024 MB")
        self.cache_usage_label.setStyleSheet("font-family: monospace;")
        layout.addWidget(self.cache_usage_label, 0, 1)

        self.cache_progress = QtWidgets.QProgressBar()
        self.cache_progress.setRange(0, 100)
        self.cache_progress.setValue(0)
        layout.addWidget(self.cache_progress, 1, 0, 1, 2)

        # Hit ratio
        layout.addWidget(QtWidgets.QLabel("Hit ratio:"), 2, 0)
        self.cache_hit_ratio_label = QtWidgets.QLabel("0.0%")
        self.cache_hit_ratio_label.setStyleSheet("font-family: monospace;")
        layout.addWidget(self.cache_hit_ratio_label, 2, 1)

        # Eviction count
        layout.addWidget(QtWidgets.QLabel("Evictions:"), 3, 0)
        self.cache_eviction_label = QtWidgets.QLabel("0")
        self.cache_eviction_label.setStyleSheet("font-family: monospace;")
        layout.addWidget(self.cache_eviction_label, 3, 1)

        # Item count
        layout.addWidget(QtWidgets.QLabel("Items:"), 4, 0)
        self.cache_items_label = QtWidgets.QLabel("0")
        self.cache_items_label.setStyleSheet("font-family: monospace;")
        layout.addWidget(self.cache_items_label, 4, 1)

        return group

    def _create_jobs_group(self) -> QtWidgets.QGroupBox:
        """Create jobs/prefetch metrics group box."""
        group = QtWidgets.QGroupBox("Active Jobs & Prefetch")
        layout = QtWidgets.QGridLayout(group)

        # Active jobs
        layout.addWidget(QtWidgets.QLabel("Active jobs:"), 0, 0)
        self.jobs_active_label = QtWidgets.QLabel("0")
        self.jobs_active_label.setStyleSheet("font-family: monospace;")
        layout.addWidget(self.jobs_active_label, 0, 1)

        # Prefetch queue depth
        layout.addWidget(QtWidgets.QLabel("Prefetch queue:"), 1, 0)
        self.prefetch_queue_label = QtWidgets.QLabel("0")
        self.prefetch_queue_label.setStyleSheet("font-family: monospace;")
        layout.addWidget(self.prefetch_queue_label, 1, 1)

        # Total processed
        layout.addWidget(QtWidgets.QLabel("Processed:"), 2, 0)
        self.jobs_processed_label = QtWidgets.QLabel("0")
        self.jobs_processed_label.setStyleSheet("font-family: monospace;")
        layout.addWidget(self.jobs_processed_label, 2, 1)

        return group

    def _create_buffer_group(self) -> QtWidgets.QGroupBox:
        """Create ring buffer metrics group box."""
        group = QtWidgets.QGroupBox("Ring Buffer")
        layout = QtWidgets.QGridLayout(group)

        # Buffer usage
        layout.addWidget(QtWidgets.QLabel("Memory:"), 0, 0)
        self.buffer_memory_label = QtWidgets.QLabel("0 MB")
        self.buffer_memory_label.setStyleSheet("font-family: monospace;")
        layout.addWidget(self.buffer_memory_label, 0, 1)

        # Buffer fill level
        layout.addWidget(QtWidgets.QLabel("Fill level:"), 1, 0)
        self.buffer_fill_label = QtWidgets.QLabel("0%")
        self.buffer_fill_label.setStyleSheet("font-family: monospace;")
        layout.addWidget(self.buffer_fill_label, 1, 1)

        # Frame count
        layout.addWidget(QtWidgets.QLabel("Frames:"), 2, 0)
        self.buffer_frames_label = QtWidgets.QLabel("0")
        self.buffer_frames_label.setStyleSheet("font-family: monospace;")
        layout.addWidget(self.buffer_frames_label, 2, 1)

        return group

    def _setup_update_timer(self) -> None:
        """Set up the periodic update timer (500ms)."""
        self._update_timer = QtCore.QTimer(self)
        self._update_timer.timeout.connect(self._update_metrics)
        self._update_timer.setInterval(500)

    def set_cache(self, cache: Optional[ProjectionCache]) -> None:
        """Connect to projection cache."""
        self.cache = cache

    def set_ring_buffer(self, ring_buffer: Optional[RingBuffer]) -> None:
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
        self._update_warnings()

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

        # Progress bar
        percent = int((mb_used / mb_budget * 100)) if mb_budget > 0 else 0
        self.cache_progress.setValue(min(100, percent))

        # Color code by usage
        if percent >= 90:
            self.cache_progress.setStyleSheet("QProgressBar::chunk { background-color: #ff6b6b; }")
        elif percent >= 75:
            self.cache_progress.setStyleSheet("QProgressBar::chunk { background-color: #ffa94d; }")
        else:
            self.cache_progress.setStyleSheet("QProgressBar::chunk { background-color: #51cf66; }")

    def _update_jobs_metrics(self) -> None:
        """Update job queue and prefetch statistics."""
        if not self.main_window:
            return

        # Get active job count from job manager
        active_count = 0
        processed_count = 0
        if hasattr(self.main_window, "jobs"):
            jobs = self.main_window.jobs
            if hasattr(jobs, "total_submitted"):
                processed_count = jobs.total_submitted
            if hasattr(jobs, "_active_tasks"):
                active_count = len(jobs._active_tasks)

        self.jobs_active_label.setText(str(active_count))
        self.jobs_processed_label.setText(str(processed_count))

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

    def _update_warnings(self) -> None:
        """Update warning messages."""
        warnings = []

        # Cache warning
        if self.cache:
            mb_used, _ = self.cache.stats()
            mb_budget = int(self.cache._max_bytes / (1024 * 1024))
            percent = (mb_used / mb_budget * 100) if mb_budget > 0 else 0
            if percent >= 90:
                warnings.append(f"⚠ Cache at {percent:.0f}% of budget")

        # Jobs warning
        if self.main_window and hasattr(self.main_window, "jobs"):
            active_count = 0
            if hasattr(self.main_window.jobs, "_active_tasks"):
                active_count = len(self.main_window.jobs._active_tasks)
            if active_count >= 5:
                warnings.append(f"⚠ {active_count} jobs running (potential slowdown)")

        # No warnings
        if not warnings:
            self.warnings_label.setText("None - Performance nominal")
            self.warnings_label.setStyleSheet("color: #51cf66; font-weight: normal;")
        else:
            self.warnings_label.setText("\n".join(warnings))
            self.warnings_label.setStyleSheet("color: #ff6b6b; font-weight: bold;")

    def reset_telemetry(self) -> None:
        """Reset cache telemetry counters."""
        if self.cache:
            self.cache.telemetry().reset()
            self._update_cache_metrics()
