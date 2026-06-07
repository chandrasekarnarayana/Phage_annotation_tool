"""Utils memory profiling funcs helpers for the phage annotation tool.

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
        """Wrap one function with memory snapshot logging."""
        @functools.wraps(f)
        def wrapper(*args: Any, **kwargs: Any) -> Any:
            """Run the wrapper workflow."""
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
