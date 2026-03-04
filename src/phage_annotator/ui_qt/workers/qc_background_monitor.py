"""Background QC monitoring worker for continuous quality checks."""

from __future__ import annotations

import time
from typing import Optional

from matplotlib.backends.qt_compat import QtCore, QtWidgets


class QCBackgroundMonitor(QtCore.QObject):
    """
    Background worker that continuously monitors annotation and image quality.
    
    Runs validation checks in a QThread to avoid blocking the UI.
    Uses two-tier monitoring:
    - Debounced response to user changes (2s after edit)
    - Periodic full scan (10s intervals)
    """
    
    # Signals
    validation_completed = QtCore.Signal()  # Emitted when validation finishes
    monitoring_started = QtCore.Signal()    # Emitted when monitor starts
    monitoring_stopped = QtCore.Signal()    # Emitted when monitor stops
    status_changed = QtCore.Signal(str)     # Emitted with status message
    
    def __init__(self):
        """Initialize background monitor."""
        super().__init__()
        
        self.is_running = False
        self.is_enabled = False  # DISABLED: QC monitoring disabled
        self.validation_callback: Optional[callable] = None
        
        # Timers for debounced + periodic checks
        self._edit_debounce_timer = QtCore.QTimer()
        self._edit_debounce_timer.setSingleShot(True)
        self._edit_debounce_timer.setInterval(2000)  # 2s debounce
        self._edit_debounce_timer.timeout.connect(self._on_edit_debounce_timeout)
        
        self._periodic_timer = QtCore.QTimer()
        self._periodic_timer.setSingleShot(False)
        self._periodic_timer.setInterval(10000)  # 10s scan interval
        self._periodic_timer.timeout.connect(self._on_periodic_timeout)
        
        # State tracking
        self._pending_edit = False
        self._pending_periodic = False
        self._last_validation_time = 0.0
    
    def start(self) -> None:
        """Start background monitoring."""
        if self.is_running:
            return
        
        self.is_running = True
        self._edit_debounce_timer.start()
        self._periodic_timer.start()
        self.monitoring_started.emit()
        self.status_changed.emit("Monitoring active")
    
    def stop(self) -> None:
        """Stop background monitoring."""
        if not self.is_running:
            return
        
        self.is_running = False
        self._edit_debounce_timer.stop()
        self._periodic_timer.stop()
        self.monitoring_stopped.emit()
        self.status_changed.emit("Monitoring paused")
    
    def on_annotation_changed(self) -> None:
        """Called when annotations are added, removed, or modified.
        
        Triggers debounced validation (2s after last change).
        """
        if not self.is_enabled or not self.is_running:
            return
        
        self._pending_edit = True
        self._edit_debounce_timer.stop()
        self._edit_debounce_timer.start()
        self.status_changed.emit("Change detected, QC pending...")
    
    def on_image_loaded(self) -> None:
        """Called when a new image is loaded.
        
        Immediately validates the newly loaded image.
        """
        if not self.is_enabled or not self.is_running:
            return
        
        # Reset timers for fresh validation
        self._pending_edit = True
        self._edit_debounce_timer.stop()
        self._edit_debounce_timer.setInterval(500)  # Faster for image load
        self._edit_debounce_timer.start()
        self.status_changed.emit("Image loaded, running QC...")
    
    def on_labels_changed(self) -> None:
        """Called when available labels change (add/remove/rename).
        
        Triggers re-validation since label constraints may be affected.
        """
        if not self.is_enabled or not self.is_running:
            return
        
        self._pending_edit = True
        self._edit_debounce_timer.stop()
        self._edit_debounce_timer.setInterval(1000)  # Moderate debounce for label changes
        self._edit_debounce_timer.start()
        self.status_changed.emit("Labels changed, QC pending...")
    
    def set_enabled(self, enabled: bool) -> None:
        """Enable or disable continuous monitoring."""
        self.is_enabled = enabled
        if enabled and not self.is_running:
            self.start()
        elif not enabled and self.is_running:
            self.stop()
    
    def set_validation_callback(self, callback: callable) -> None:
        """Set the callback function to call for validation.
        
        Callback should accept no arguments and perform QC validation.
        """
        self.validation_callback = callback
    
    def _on_edit_debounce_timeout(self) -> None:
        """Debounce timer fired: run validation for user changes."""
        self._edit_debounce_timer.setInterval(2000)  # Reset to standard 2s
        
        if self._pending_edit and self.validation_callback:
            self._pending_edit = False
            self.status_changed.emit("Running QC check...")
            
            try:
                self.validation_callback()
                self.validation_completed.emit()
                self.status_changed.emit("QC check complete")
            except Exception as e:
                self.status_changed.emit(f"QC check error: {str(e)}")
    
    def _on_periodic_timeout(self) -> None:
        """Periodic timer fired: run full background validation scan."""
        # Only run periodic if enough time has passed since last validation
        elapsed = time.time() - self._last_validation_time
        if elapsed < 9.0:  # Avoid overlap with debounced checks
            return
        
        if self.validation_callback:
            self._last_validation_time = time.time()
            self.status_changed.emit("Periodic QC scan in progress...")
            
            try:
                self.validation_callback()
                self.validation_completed.emit()
                self.status_changed.emit("Periodic scan complete")
            except Exception as e:
                self.status_changed.emit(f"Periodic scan error: {str(e)}")


class QCMonitorStatusWidget(QtWidgets.QWidget):
    """Visual indicator showing background QC monitor status."""
    
    def __init__(self, parent: Optional[QtWidgets.QWidget] = None):
        """Initialize status widget."""
        super().__init__(parent)
        
        layout = QtWidgets.QHBoxLayout(self)
        layout.setContentsMargins(2, 2, 2, 2)
        layout.setSpacing(3)
        
        # Status indicator (pulsing dot)
        self.indicator = QtWidgets.QLabel("●")
        self.indicator.setStyleSheet(
            "QLabel { color: #4caf50; font-size: 12px; margin: 0px; }"
        )
        layout.addWidget(self.indicator)
        
        # Status message
        self.status_label = QtWidgets.QLabel("Monitoring...")
        self.status_label.setStyleSheet(
            "QLabel { color: #4caf50; font-size: 10px; font-style: italic; }"
        )
        self.status_label.setMaximumWidth(150)
        layout.addWidget(self.status_label)
        
        layout.addStretch()
        
        # Pulsing animation timer
        self._pulse_timer = QtCore.QTimer()
        self._pulse_timer.setInterval(500)
        self._pulse_timer.timeout.connect(self._on_pulse_tick)
        self._pulse_state = 0
        
        self.setMaximumHeight(20)
    
    def set_monitoring_active(self, active: bool) -> None:
        """Show/hide monitoring indicator."""
        if active:
            self.show()
            self._pulse_timer.start()
        else:
            self._pulse_timer.stop()
            self.hide()
    
    def set_status(self, message: str) -> None:
        """Update status message."""
        # Truncate long messages
        if len(message) > 25:
            message = message[:22] + "..."
        self.status_label.setText(message)
    
    def _on_pulse_tick(self) -> None:
        """Animate pulsing indicator."""
        self._pulse_state = (self._pulse_state + 1) % 2
        opacity = 0.5 if self._pulse_state == 0 else 1.0
        self.indicator.setStyleSheet(
            f"QLabel {{ color: #4caf50; font-size: 12px; opacity: {opacity}; margin: 0px; }}"
        )
