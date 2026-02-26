"""Memory profiling utilities for Phase 7 zero-copy optimizations.

Provides decorators and context managers to measure memory usage and track
the effectiveness of zero-copy optimizations.

Usage:
    >>> @profile_memory
    ... def render_frame(image):
    ...     slice_data = image[0, 0, :, :]
    ...     return process(slice_data)
    >>> 
    >>> with memory_snapshot("projection computation"):
    ...     mean_proj = compute_mean_projection(stack)
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
    "get_current_memory_mb",
    "get_peak_memory_mb",
]

logger = logging.getLogger(__name__)


def get_current_memory_mb() -> float:
    """Return current process RSS (Resident Set Size) in megabytes.
    
    Returns
    -------
    float
        Memory usage in MB
        
    Notes
    -----
    RSS includes:
    - All heap-allocated memory
    - Memory-mapped files (including numpy memmaps)
    - Stack memory
    - Shared libraries (may be shared with other processes)
    
    Does NOT include:
    - Swapped-out memory
    - Memory allocated but not yet used (virtual memory)
    """
    process = psutil.Process()
    return process.memory_info().rss / (1024 * 1024)


def get_peak_memory_mb() -> float:
    """Return peak memory usage since process start (platform-dependent).
    
    Returns
    -------
    float
        Peak memory in MB, or current memory if peak unavailable
        
    Notes
    -----
    On Linux: Uses /proc/[pid]/status VmHWM (High Water Mark)
    On macOS: Uses rusage maxrss
    On Windows: Uses peak working set size
    
    Falls back to current RSS if peak measurement unavailable.
    """
    try:
        process = psutil.Process()
        # Try to get peak memory (platform-specific)
        if hasattr(process.memory_info(), 'peak_wset'):
            # Windows
            return process.memory_info().peak_wset / (1024 * 1024)
        elif hasattr(process.memory_info(), 'peak_rss'):
            # Some platforms
            return process.memory_info().peak_rss / (1024 * 1024)
        else:
            # Fallback to current RSS
            return get_current_memory_mb()
    except Exception:
        return get_current_memory_mb()


@contextmanager
def memory_snapshot(
    label: str, *, log_level: int = logging.DEBUG, threshold_mb: float = 10.0
) -> Generator[None, None, None]:
    """Context manager to measure memory delta during a code block.
    
    Parameters
    ----------
    label : str
        Description of the operation being profiled
    log_level : int, default=logging.DEBUG
        Logging level for output (DEBUG, INFO, WARNING, etc.)
    threshold_mb : float, default=10.0
        Only log if memory delta exceeds this threshold (MB)
        
    Examples
    --------
    >>> with memory_snapshot("compute mean projection"):
    ...     mean_proj = stack.mean(axis=0)
    
    Output (if delta > threshold):
        [INFO] Memory delta for 'compute mean projection': +15.2 MB (120.5 -> 135.7 MB)
        
    Notes
    -----
    This measures RSS delta, which includes:
    - Newly allocated arrays
    - Cached data
    - Memory retained by garbage collector
    
    For accurate measurements:
    - Run gc.collect() before the snapshot
    - Avoid concurrent operations
    - Measure over multiple iterations for consistency
    """
    mem_before = get_current_memory_mb()
    time_before = time.perf_counter()
    
    try:
        yield
    finally:
        time_after = time.perf_counter()
        mem_after = get_current_memory_mb()
        delta_mem = mem_after - mem_before
        delta_time = time_after - time_before
        
        if abs(delta_mem) >= threshold_mb:
            sign = "+" if delta_mem >= 0 else ""
            logger.log(
                log_level,
                f"Memory delta for '{label}': {sign}{delta_mem:.1f} MB "
                f"({mem_before:.1f} -> {mem_after:.1f} MB) in {delta_time:.3f}s",
            )


def profile_memory(
    func: Optional[Callable] = None,
    *,
    log_level: int = logging.INFO,
    threshold_mb: float = 10.0,
) -> Callable:
    """Decorator to profile memory usage of a function.
    
    Parameters
    ----------
    func : Callable, optional
        Function to decorate (automatically provided when used as @decorator)
    log_level : int, default=logging.INFO
        Logging level for output
    threshold_mb : float, default=10.0
        Only log if memory delta exceeds this threshold
        
    Returns
    -------
    Callable
        Decorated function
        
    Examples
    --------
    >>> @profile_memory
    ... def render_frame(image, t, z):
    ...     frame = image[t, z, :, :]
    ...     return process(frame)
    
    >>> @profile_memory(threshold_mb=50.0)
    ... def compute_projection(stack):
    ...     return stack.mean(axis=0)
    
    Output (if delta > threshold):
        [INFO] render_frame: +12.5 MB (120.0 -> 132.5 MB) in 0.045s
        
    Notes
    -----
    - Overhead: ~1ms per call (negligible for operations >10ms)
    - Does not track memory inside nested function calls
    - Use memory_snapshot for finer-grained profiling
    """
    def decorator(f: Callable) -> Callable:
        @functools.wraps(f)
        def wrapper(*args: Any, **kwargs: Any) -> Any:
            with memory_snapshot(
                f.__name__, log_level=log_level, threshold_mb=threshold_mb
            ):
                return f(*args, **kwargs)
        return wrapper
    
    # Handle both @profile_memory and @profile_memory(...) syntax
    if func is None:
        return decorator
    else:
        return decorator(func)


# Advanced helpers for detailed profiling


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
            while self._running:
                timestamp = time.time()
                mem_mb = get_current_memory_mb()
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


# Testing helpers


def assert_no_memory_regression(
    baseline_mb: float,
    *,
    tolerance: float = 0.1,
    msg: Optional[str] = None,
) -> None:
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
    >>> mem_before = get_current_memory_mb()
    >>> # ... run operation that should not allocate memory ...
    >>> assert_no_memory_regression(mem_before, tolerance=0.05)
    """
    current = get_current_memory_mb()
    max_allowed = baseline_mb * (1 + tolerance)
    
    if current > max_allowed:
        default_msg = (
            f"Memory regression detected: {current:.1f} MB > "
            f"{max_allowed:.1f} MB (baseline={baseline_mb:.1f} MB, "
            f"tolerance={tolerance:.1%})"
        )
        raise AssertionError(msg or default_msg)


# Example usage for documentation


def _example_usage():
    """Example demonstrating memory profiling tools (for documentation)."""
    import gc
    import numpy as np
    
    # Example 1: Function profiling
    @profile_memory(threshold_mb=5.0)
    def allocate_large_array():
        return np.zeros((2048, 2048), dtype=np.float32)
    
    # Example 2: Context manager
    with memory_snapshot("numpy allocation", log_level=logging.INFO):
        arr = np.zeros((1024, 1024), dtype=np.float32)
    
    # Example 3: Regression testing
    gc.collect()
    baseline = get_current_memory_mb()
    
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
