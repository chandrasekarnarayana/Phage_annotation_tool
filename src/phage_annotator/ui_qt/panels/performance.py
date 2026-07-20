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


from phage_annotator.ui_qt.panels.performance_panel_widgets import PerformancePanelWidgetsMixin
from phage_annotator.ui_qt.panels.performance_panel_metrics import PerformancePanelMetricsMixin
from phage_annotator.ui_qt.panels.suggestion_generation import SuggestionGenerationMixin as PerformanceTelemetryMixin

class PerformancePanel(
    PerformancePanelWidgetsMixin,
    PerformancePanelMetricsMixin,
    PerformanceTelemetryMixin,
    QtWidgets.QWidget,
):
    """Real-time performance metrics panel for cache, jobs, and buffers.

Displays:
- Cache: Memory usage, hit ratio, eviction count
- Jobs: Active count, prefetch queue depth
- Buffers: Ring buffer memory usage
- Warnings: 90% cache threshold, job queue saturation"""

    pass
