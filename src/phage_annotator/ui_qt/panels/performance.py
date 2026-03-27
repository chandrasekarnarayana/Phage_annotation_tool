"""Consolidated performance monitoring panel for cache, jobs, and buffers.

P5.1 Implementation: Real-time performance metrics dashboard showing:
  - Projection cache usage (MB / budget, hit ratio, eviction count)
  - Active job count and prefetch queue status
  - Ring buffer memory usage
  - Performance warnings (cache at 90% budget, jobs backing up)

P3a Implementation: Memory Pressure Monitoring
  - System RAM availability tracking (psutil)
  - Memory pressure levels: LOW (>80%), MEDIUM (20-80%), HIGH (<20%)
  - Auto-mitigation when pressure detected (disable prefetch, reduce tile size)

The panel updates every 500ms when visible and integrates with the session
state, cache telemetry, job queue, and ring buffer management.
"""

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
