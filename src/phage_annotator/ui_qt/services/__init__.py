"""Qt-specific service implementations and bridges.

This package contains Qt-aware wrappers for framework services:
- settings_qt.py: QSettings-backed SettingsService
- event_qt.py: Qt signal-based EventService (optional)  
- log_qt.py: QTextEdit logging sink
- threading_qt.py: Qt thread pool integration

These enable the framework services to work seamlessly with Qt's event loop.
"""

__all__ = []
