"""Per-modality playback FPS control widget."""

from __future__ import annotations

from typing import Optional, Dict, Callable

from PyQt5 import QtCore, QtWidgets


class ModalityFpsControl(QtWidgets.QWidget):
    """Widget providing FPS control for per-modality playback.
    
    Handles:
    - Displaying current FPS for selected modality
    - Updating FPS when spinbox changes
    - Responding to modality selection changes
    - Syncing with playback manager
    
    Signals
    -------
    fps_changed : pyqtSignal(int, float)
        Emitted when FPS changes (modality_idx, new_fps).
    """
    
    fps_changed = QtCore.pyqtSignal(int, float)  # modality_idx, fps
    
    def __init__(self, parent: Optional[QtWidgets.QWidget] = None):
        """Initialize FPS control.
        
        Parameters
        ----------
        parent : QtWidgets.QWidget, optional
            Parent widget.
        """
        super().__init__(parent)
        self._current_modality_idx: Optional[int] = None
        self._modality_fps: Dict[int, float] = {}
        self._playback_manager: Optional[object] = None
        self._updating = False
        
        self._init_ui()
    
    def _init_ui(self) -> None:
        """Initialize UI elements."""
        layout = QtWidgets.QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        
        # Label
        self.label = QtWidgets.QLabel("FPS:")
        layout.addWidget(self.label)
        
        # Spinbox for FPS value
        self.fps_spinbox = QtWidgets.QDoubleSpinBox()
        self.fps_spinbox.setMinimum(0.1)
        self.fps_spinbox.setMaximum(120.0)
        self.fps_spinbox.setValue(10.0)
        self.fps_spinbox.setSingleStep(1.0)
        self.fps_spinbox.setDecimals(1)
        self.fps_spinbox.setToolTip("Frames per second for active modality")
        self.fps_spinbox.setSuffix(" fps")
        self.fps_spinbox.setMaximumWidth(80)
        self.fps_spinbox.valueChanged.connect(self._on_fps_changed)
        layout.addWidget(self.fps_spinbox)
        
        # Reset button
        self.reset_btn = QtWidgets.QPushButton("Reset")
        self.reset_btn.setMaximumWidth(60)
        self.reset_btn.setToolTip("Reset to default FPS (10.0)")
        self.reset_btn.clicked.connect(self._on_reset_fps)
        layout.addWidget(self.reset_btn)
        
        layout.addStretch()
    
    def set_playback_manager(self, manager: object) -> None:
        """Set the playback manager reference.
        
        Parameters
        ----------
        manager : object
            ModalityPlaybackManager instance.
        """
        self._playback_manager = manager
    
    def set_active_modality(self, modality_idx: int, modality_name: str) -> None:
        """Update UI for newly selected modality.
        
        Parameters
        ----------
        modality_idx : int
            Index of active modality.
        modality_name : str
            Display name for label updating.
        """
        self._current_modality_idx = modality_idx
        
        # Get FPS from manager or stored values
        if self._playback_manager is not None:
            state = self._playback_manager.get_state(modality_idx)
            if state is not None:
                fps = state.fps
            else:
                fps = self._modality_fps.get(modality_idx, 10.0)
        else:
            fps = self._modality_fps.get(modality_idx, 10.0)
        
        # Block signals while updating
        self.fps_spinbox.blockSignals(True)
        self.fps_spinbox.setValue(fps)
        self.label.setText(f"FPS ({modality_name}):")
        self.fps_spinbox.blockSignals(False)
        
        # Store for later reference
        self._modality_fps[modality_idx] = fps
    
    def _on_fps_changed(self, value: float) -> None:
        """Handle FPS spinbox value change.
        
        Parameters
        ----------
        value : float
            New FPS value.
        """
        if self._updating or self._current_modality_idx is None:
            return
        
        # Clamp value
        value = max(0.1, min(120.0, value))
        
        # Store value
        self._modality_fps[self._current_modality_idx] = value
        
        # Update playback manager if available
        if self._playback_manager is not None:
            self._playback_manager.set_fps(self._current_modality_idx, value)
        
        # Emit signal
        self.fps_changed.emit(self._current_modality_idx, value)
    
    def _on_reset_fps(self) -> None:
        """Reset FPS to default value."""
        self.fps_spinbox.setValue(10.0)
    
    def get_fps(self, modality_idx: int) -> float:
        """Get stored FPS for a modality.
        
        Parameters
        ----------
        modality_idx : int
            Modality index.
        
        Returns
        -------
        float
            FPS value, or 10.0 if not set.
        """
        return self._modality_fps.get(modality_idx, 10.0)
    
    def set_fps(self, modality_idx: int, fps: float) -> None:
        """Set FPS for a modality.
        
        Parameters
        ----------
        modality_idx : int
            Modality index.
        fps : float
            FPS value.
        """
        fps = max(0.1, min(120.0, fps))
        self._modality_fps[modality_idx] = fps
        
        # Update UI if this is the active modality
        if modality_idx == self._current_modality_idx:
            self._updating = True
            self.fps_spinbox.setValue(fps)
            self._updating = False
        
        # Update playback manager
        if self._playback_manager is not None:
            self._playback_manager.set_fps(modality_idx, fps)
    
    def register_modality(self, modality_idx: int, fps: float = 10.0) -> None:
        """Register a modality with initial FPS.
        
        Parameters
        ----------
        modality_idx : int
            Modality index.
        fps : float, optional
            Initial FPS value (default: 10.0).
        """
        self._modality_fps[modality_idx] = max(0.1, fps)
