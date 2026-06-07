"""Qt-specific ThreadService implementation using QThreadPool.

Provides thread management using Qt's QThreadPool for integration
with Qt's event loop and signal/slot mechanisms.
"""

from __future__ import annotations

from typing import Callable, Optional
try:
    from PyQt5.QtCore import QThreadPool, QRunnable, pyqtSignal, QObject
except ImportError:
    QThreadPool = None
    QRunnable = None

from phage_annotator.framework.services import ThreadService


class QtRunnable(QRunnable):
    """QRunnable wrapper for Python functions."""
    
    def __init__(self, func: Callable, *args, **kwargs):
        """Initialize the object and prepare its runtime state."""
        super().__init__()
        self.func = func
        self.args = args
        self.kwargs = kwargs
    
    def run(self):
        """Execute the wrapped function."""
        try:
            self.func(*self.args, **self.kwargs)
        except Exception:
            pass  # Silently handle exceptions


class QtThreadService(ThreadService):
    """Qt-based thread service using QThreadPool."""
    
    def __init__(self, max_threads: int = 4):
        """Initialize Qt thread service.
        
        Args:
            max_threads: Maximum number of worker threads
        """
        if QThreadPool is None:
            raise ImportError("PyQt5 is required for QtThreadService")
        
        self.pool = QThreadPool()
        self.pool.setMaxThreadCount(max_threads)
    
    def execute(self, func: Callable, *args, **kwargs) -> None:
        """Execute function in a thread pool.
        
        Args:
            func: Function to execute
            *args: Positional arguments
            **kwargs: Keyword arguments
        """
        runnable = QtRunnable(func, *args, **kwargs)
        self.pool.start(runnable)
    
    def wait_completion(self) -> None:
        """Wait for all threads to complete."""
        self.pool.waitForDone()
    
    def set_max_threads(self, count: int) -> None:
        """Set maximum thread count.
        
        Args:
            count: Maximum number of threads
        """
        self.pool.setMaxThreadCount(count)
    
    def active_threads(self) -> int:
        """Get number of active threads."""
        return self.pool.activeThreadCount()
    
    def shutdown(self) -> None:
        """Shutdown thread pool."""
        self.pool.waitForDone()
