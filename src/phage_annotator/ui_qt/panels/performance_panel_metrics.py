"""Extracted method group 1 for PerformancePanel."""

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



class PerformancePanelMetricsMixin:
    """Method group 1 extracted from PerformancePanel."""

    def __init__(self, parent: Optional[MainWindow] = None) -> None:
        """Initialize the object and prepare its runtime state."""
        super().__init__(parent)
        self.main_window = parent
        self.cache: Optional[ProjectionCache] = None
        self.ring_buffer: Optional[FrameRingBuffer] = None
        self._update_timer: Optional[QtCore.QTimer] = None
        self._memory_pressure_active = False  # P3a: Track memory pressure state
        self._last_prefetch_disabled = False  # P3b: Track prefetch mitigation
        self._cache_pressure_active = False
        
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

        # Array pool section (P5)
        pool_group = self._create_pool_group()
        layout.addWidget(pool_group)

        # System memory section (P3a)
        if HAS_PSUTIL:
            memory_group = self._create_memory_group()
            layout.addWidget(memory_group)

        # Warnings/alerts section
        self.warnings_label = QtWidgets.QLabel()
        self.warnings_label.setWordWrap(True)
        self.warnings_label.setStyleSheet("color: #ff6b6b; font-weight: bold;")
        layout.addWidget(QtWidgets.QLabel("Warnings:"))
        layout.addWidget(self.warnings_label)

        # Refresh button
        actions_row = QtWidgets.QHBoxLayout()
        refresh_btn = QtWidgets.QPushButton("Force Refresh")
        refresh_btn.clicked.connect(self._update_metrics)
        actions_row.addWidget(refresh_btn)
        self.clear_cache_btn = QtWidgets.QPushButton("Clear Cache")
        self.clear_cache_btn.clicked.connect(self._clear_projection_cache)
        actions_row.addWidget(self.clear_cache_btn)
        actions_row.addStretch(1)
        layout.addLayout(actions_row)

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

        # Thrashing indicator (P1a)
        layout.addWidget(QtWidgets.QLabel("Thrashing:"), 5, 0)
        self.cache_thrashing_label = QtWidgets.QLabel("NO")
        self.cache_thrashing_label.setStyleSheet("font-family: monospace;")
        layout.addWidget(self.cache_thrashing_label, 5, 1)

        # LOD mode indicator (P2a)
        layout.addWidget(QtWidgets.QLabel("LOD mode:"), 6, 0)
        self.cache_lod_mode_label = QtWidgets.QLabel("OFF")
        self.cache_lod_mode_label.setStyleSheet("font-family: monospace;")
        layout.addWidget(self.cache_lod_mode_label, 6, 1)

        # Component memory tracking (P7e)
        layout.addWidget(QtWidgets.QLabel("Main proj:"), 7, 0)
        self.cache_component_main_label = QtWidgets.QLabel("0 MB")
        self.cache_component_main_label.setStyleSheet("font-family: monospace;")
        layout.addWidget(self.cache_component_main_label, 7, 1)

        layout.addWidget(QtWidgets.QLabel("Pyramid:"), 8, 0)
        self.cache_component_pyramid_label = QtWidgets.QLabel("0 MB")
        self.cache_component_pyramid_label.setStyleSheet("font-family: monospace;")
        layout.addWidget(self.cache_component_pyramid_label, 8, 1)

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

        layout.addWidget(QtWidgets.QLabel("Pending queue:"), 3, 0)
        self.jobs_pending_label = QtWidgets.QLabel("0 / 0")
        self.jobs_pending_label.setStyleSheet("font-family: monospace;")
        layout.addWidget(self.jobs_pending_label, 3, 1)

        layout.addWidget(QtWidgets.QLabel("Blocked:"), 4, 0)
        self.jobs_blocked_label = QtWidgets.QLabel("0")
        self.jobs_blocked_label.setStyleSheet("font-family: monospace;")
        layout.addWidget(self.jobs_blocked_label, 4, 1)

        layout.addWidget(QtWidgets.QLabel("Queue state:"), 5, 0)
        self.jobs_queue_summary_label = QtWidgets.QLabel("Idle")
        self.jobs_queue_summary_label.setWordWrap(True)
        self.jobs_queue_summary_label.setStyleSheet("font-family: monospace;")
        layout.addWidget(self.jobs_queue_summary_label, 5, 1)

        layout.addWidget(QtWidgets.QLabel("Queue detail:"), 6, 0)
        self.jobs_queue_list = QtWidgets.QListWidget()
        self.jobs_queue_list.setMaximumHeight(120)
        layout.addWidget(self.jobs_queue_list, 6, 1)

        actions_row = QtWidgets.QHBoxLayout()
        self.jobs_cancel_queued_btn = QtWidgets.QPushButton("Cancel Queued")
        self.jobs_cancel_queued_btn.setToolTip("Cancel queued jobs that have not started yet.")
        self.jobs_cancel_queued_btn.clicked.connect(self._cancel_queued_jobs)
        actions_row.addWidget(self.jobs_cancel_queued_btn)
        self.jobs_cancel_blocked_btn = QtWidgets.QPushButton("Cancel Blocked")
        self.jobs_cancel_blocked_btn.setToolTip("Cancel queued jobs currently waiting on dependencies.")
        self.jobs_cancel_blocked_btn.clicked.connect(self._cancel_blocked_jobs)
        actions_row.addWidget(self.jobs_cancel_blocked_btn)
        actions_row.addStretch(1)
        layout.addLayout(actions_row, 7, 0, 1, 2)

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
    def _create_pool_group(self) -> QtWidgets.QGroupBox:
        """Create array pool telemetry group box (P5)."""
        group = QtWidgets.QGroupBox("Array Pool (P5)")
        layout = QtWidgets.QGridLayout(group)

        layout.addWidget(QtWidgets.QLabel("Hits:"), 0, 0)
        self.pool_hits_label = QtWidgets.QLabel("0")
        self.pool_hits_label.setStyleSheet("font-family: monospace;")
        layout.addWidget(self.pool_hits_label, 0, 1)

        layout.addWidget(QtWidgets.QLabel("Misses:"), 1, 0)
        self.pool_misses_label = QtWidgets.QLabel("0")
        self.pool_misses_label.setStyleSheet("font-family: monospace;")
        layout.addWidget(self.pool_misses_label, 1, 1)

        layout.addWidget(QtWidgets.QLabel("Hit rate:"), 2, 0)
        self.pool_hit_rate_label = QtWidgets.QLabel("0.0%")
        self.pool_hit_rate_label.setStyleSheet("font-family: monospace;")
        layout.addWidget(self.pool_hit_rate_label, 2, 1)

        layout.addWidget(QtWidgets.QLabel("Entries:"), 3, 0)
        self.pool_entries_label = QtWidgets.QLabel("0")
        self.pool_entries_label.setStyleSheet("font-family: monospace;")
        layout.addWidget(self.pool_entries_label, 3, 1)

        layout.addWidget(QtWidgets.QLabel("Drops:"), 4, 0)
        self.pool_drops_label = QtWidgets.QLabel("0")
        self.pool_drops_label.setStyleSheet("font-family: monospace;")
        layout.addWidget(self.pool_drops_label, 4, 1)

        return group
