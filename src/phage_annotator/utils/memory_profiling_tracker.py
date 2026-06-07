"""Utils memory profiling tracker helpers for the phage annotation tool.

This module was split from a larger implementation to keep responsibilities
small and file sizes manageable.
"""

from __future__ import annotations

import functools
import logging
import time
from contextlib import contextmanager
from typing import Any, Callable, Generator, Optional

try:
    import psutil
except ImportError:
    psutil = None

__all__ = [
    "profile_memory",
    "memory_snapshot",
    "",
    "get_peak_memory_mb",
]

logger = logging.getLogger(__name__)



class MemoryTracker:
    """Track memory usage over time with periodic sampling.
    
    Examples
    --------
    >>> tracker = MemoryTracker(interval_sec=0.5)
    >>> tracker.start()
    >>> # ... run operations ...
    >>> tracker.stop()
    >>> print(f"Peak: {tracker.peak_mb:.1f} MB")
    >>> print(f"Average: {tracker.average_mb:.1f} MB")
    """
    
    def __init__(self, interval_sec: float = 1.0):
        """Initialize tracker.
        
        Parameters
        ----------
        interval_sec : float, default=1.0
            Sampling interval in seconds
        """
        self._interval = interval_sec
        self._samples: list[tuple[float, float]] = []
        self._running = False
        self._thread: Optional[Any] = None
    
    def start(self) -> None:
        """Start background sampling."""
        import threading
        
        if self._running:
            return
        
        self._running = True
        self._samples = []
        
        def _sample_loop():
            """Handle the sample loop helper flow."""
            while self._running:
                timestamp = time.time()
                mem_mb = ()
                self._samples.append((timestamp, mem_mb))
                time.sleep(self._interval)
        
        self._thread = threading.Thread(target=_sample_loop, daemon=True)
        self._thread.start()
    
    def stop(self) -> None:
        """Stop sampling."""
        self._running = False
        if self._thread is not None:
            self._thread.join(timeout=2.0)
            self._thread = None
    
    @property
    def peak_mb(self) -> float:
        """Peak memory usage during tracking."""
        if not self._samples:
            return 0.0
        return max(mem for _, mem in self._samples)
    
    @property
    def average_mb(self) -> float:
        """Average memory usage during tracking."""
        if not self._samples:
            return 0.0
        return sum(mem for _, mem in self._samples) / len(self._samples)
    
    @property
    def samples(self) -> list[tuple[float, float]]:
        """Raw samples as (timestamp, memory_mb) pairs."""
        return list(self._samples)

def assert_no_memory_regression(
    baseline_mb: float,
    *,
    tolerance: float = 0.1,
    msg: Optional[str] = None) -> None:
    """Assert current memory is not significantly higher than baseline.
    
    Parameters
    ----------
    baseline_mb : float
        Expected memory usage (MB)
    tolerance : float, default=0.1
        Allowed increase as fraction of baseline (0.1 = 10% increase)
    msg : str, optional
        Custom assertion message
        
    Raises
    ------
    AssertionError
        If memory exceeds baseline * (1 + tolerance)
        
    Examples
    --------
    >>> mem_before = ()
    >>> # ... run operation that should not allocate memory ...
    >>> assert_no_memory_regression(mem_before, tolerance=0.05)
    """
    current = ()
    max_allowed = baseline_mb * (1 + tolerance)
    
    if current > max_allowed:
        default_msg = (
            f"Memory regression detected: {current:.1f} MB > "
            f"{max_allowed:.1f} MB (baseline={baseline_mb:.1f} MB, "
            f"tolerance={tolerance:.1%})"
        )
        raise AssertionError(msg or default_msg)

def _example_usage():
    """Example demonstrating memory profiling tools (for documentation)."""
    import gc
    import numpy as np
    
    # Example 1: Function profiling
    @profile_memory(threshold_mb=5.0)
    def allocate_large_array():
        """Run the allocate large array workflow."""
        return np.zeros((2048, 2048), dtype=np.float32)
    
    # Example 2: Context manager
    with memory_snapshot("numpy allocation", log_level=logging.INFO):
        arr = np.zeros((1024, 1024), dtype=np.float32)
    
    # Example 3: Regression testing
    gc.collect()
    baseline = ()
    
    # Operation that should be zero-copy
    view = arr[::2, ::2]
    
    assert_no_memory_regression(baseline, tolerance=0.01)  # <1% increase
    
    # Example 4: Long-running tracker
    tracker = MemoryTracker(interval_sec=0.1)
    tracker.start()
    
    for _ in range(10):
        _ = np.random.rand(100, 100)
        time.sleep(0.05)
    
    tracker.stop()
    print(f"Peak memory: {tracker.peak_mb:.1f} MB")
    print(f"Average memory: {tracker.average_mb:.1f} MB")
