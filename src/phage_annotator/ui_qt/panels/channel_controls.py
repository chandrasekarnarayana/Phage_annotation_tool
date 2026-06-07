"""Channel control panel for multi-channel display management."""

from __future__ import annotations

from typing import Callable, Dict, Optional

from matplotlib.backends.qt_compat import QtCore, QtWidgets

from phage_annotator.data.channel_display import (
    BlendMode,
    BLEND_MODE_NAMES,
    MultiChannelDisplaySettings,
)
from phage_annotator.ui_qt.rendering.lut_manager import LUTS


class ChannelControlPanel(QtWidgets.QWidget):
    """Panel widget for per-channel display control.
    
    Provides:
    - Per-channel visibility toggle
    - Per-channel opacity slider
    - Per-channel LUT selector
    - Global blend mode selector
    """
    
    # Signals
    channel_visibility_changed = QtCore.pyqtSignal(int, bool)  # channel_idx, visible
    channel_opacity_changed = QtCore.pyqtSignal(int, float)    # channel_idx, opacity
    channel_lut_changed = QtCore.pyqtSignal(int, int)          # channel_idx, lut_idx
    blend_mode_changed = QtCore.pyqtSignal(str)                # blend_mode value
    
    def __init__(self, parent=None):
        """Initialize the object and prepare its runtime state."""
        super().__init__(parent)
        self.setObjectName("ChannelControlPanel")
        
        # State
        self.settings: Optional[MultiChannelDisplaySettings] = None
        self._updating_ui = False
        
        # Build UI
        self._build_ui()
    
    def _build_ui(self) -> None:
        """Build the channel control panel UI."""
        central_widget = QtWidgets.QWidget()
        layout = QtWidgets.QVBoxLayout(central_widget)
        layout.setContentsMargins(4, 4, 4, 4)
        layout.setSpacing(4)
        
        # Blend mode selector
        blend_group = QtWidgets.QGroupBox("Blend Mode")
        blend_layout = QtWidgets.QHBoxLayout(blend_group)
        self.blend_combo = QtWidgets.QComboBox()
        for mode in BlendMode:
            self.blend_combo.addItem(BLEND_MODE_NAMES[mode], mode.value)
        self.blend_combo.currentIndexChanged.connect(self._on_blend_mode_changed)
        blend_layout.addWidget(self.blend_combo)
        layout.addWidget(blend_group)
        
        # Channel list (scrollable)
        scroll_area = QtWidgets.QScrollArea()
        scroll_area.setWidgetResizable(True)
        scroll_widget = QtWidgets.QWidget()
        self.channels_layout = QtWidgets.QVBoxLayout(scroll_widget)
        self.channels_layout.setSpacing(8)
        scroll_area.setWidget(scroll_widget)
        layout.addWidget(scroll_area)
        
        # Stretch at bottom
        layout.addStretch()
        
        # Action buttons (at bottom)
        button_layout = QtWidgets.QHBoxLayout()
        self.reset_button = QtWidgets.QPushButton("Reset All")
        self.reset_button.clicked.connect(self._on_reset_all)
        button_layout.addWidget(self.reset_button)
        layout.addLayout(button_layout)
        
        root_layout = QtWidgets.QVBoxLayout(self)
        root_layout.setContentsMargins(0, 0, 0, 0)
        root_layout.addWidget(central_widget)
    
    def set_channel_settings(self, settings: MultiChannelDisplaySettings) -> None:
        """Update the panel with new channel settings.
        
        Parameters
        ----------
        settings : MultiChannelDisplaySettings
            Display settings for all channels.
        """
        self.settings = settings
        self._populate_channels()
    
    def _populate_channels(self) -> None:
        """Populate channel controls from current settings."""
        if self.settings is None:
            return
        
        # Clear existing channel widgets
        while self.channels_layout.count() > 0:
            item = self.channels_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()
        
        # Add channel controls
        for channel_state in self.settings.channels:
            ch_idx = channel_state.channel_idx
            widget = self._create_channel_widget(ch_idx, channel_state)
            self.channels_layout.addWidget(widget)
        
        # Update blend mode combo
        self._updating_ui = True
        try:
            blend_mode = self.settings.blend_mode.value
            self.blend_combo.setCurrentText(BLEND_MODE_NAMES[self.settings.blend_mode])
        finally:
            self._updating_ui = False
    
    def _create_channel_widget(self, channel_idx: int, state) -> QtWidgets.QWidget:
        """Create a widget for controlling one channel."""
        if not hasattr(self, '_channel_widgets'):
            self._channel_widgets = {}
        
        widget = QtWidgets.QGroupBox(f"Channel {channel_idx}")
        layout = QtWidgets.QVBoxLayout(widget)
        layout.setSpacing(4)
        
        # Visibility toggle
        visibility_layout = QtWidgets.QHBoxLayout()
        visibility_check = QtWidgets.QCheckBox("Visible")
        visibility_check.setChecked(state.visible)
        visibility_check.stateChanged.connect(
            lambda checked: self._on_channel_visibility_changed(channel_idx, checked)
        )
        visibility_layout.addWidget(visibility_check)
        visibility_layout.addStretch()
        layout.addLayout(visibility_layout)
        
        # Opacity slider
        opacity_layout = QtWidgets.QHBoxLayout()
        opacity_label = QtWidgets.QLabel("Opacity:")
        opacity_slider = QtWidgets.QSlider(QtCore.Qt.Horizontal)
        opacity_slider.setRange(0, 100)
        opacity_slider.setValue(int(state.opacity * 100))
        opacity_value_label = QtWidgets.QLabel(f"{state.opacity*100:.0f}%")
        opacity_value_label.setMaximumWidth(40)
        opacity_slider.valueChanged.connect(
            lambda val: self._on_channel_opacity_changed(channel_idx, val, opacity_value_label)
        )
        opacity_layout.addWidget(opacity_label)
        opacity_layout.addWidget(opacity_slider)
        opacity_layout.addWidget(opacity_value_label)
        layout.addLayout(opacity_layout)
        
        # LUT selector
        lut_layout = QtWidgets.QHBoxLayout()
        lut_label = QtWidgets.QLabel("LUT:")
        lut_combo = QtWidgets.QComboBox()
        for i, lut_spec in enumerate(LUTS):
            lut_combo.addItem(lut_spec.name, i)
        lut_combo.setCurrentIndex(min(state.lut, len(LUTS) - 1))
        lut_combo.currentIndexChanged.connect(
            lambda idx: self._on_channel_lut_changed(channel_idx, idx)
        )
        lut_layout.addWidget(lut_label)
        lut_layout.addWidget(lut_combo)
        layout.addLayout(lut_layout)
        
        # Store references for later access
        self._channel_widgets[channel_idx] = {
            'widget': widget,
            'visibility': visibility_check,
            'opacity_slider': opacity_slider,
            'opacity_label': opacity_value_label,
            'lut_combo': lut_combo,
        }
        
        return widget
    
    def _on_channel_visibility_changed(self, channel_idx: int, checked: bool) -> None:
        """Handle visibility toggle."""
        if self._updating_ui:
            return
        visible = bool(checked)
        if self.settings:
            self.settings.set_channel_visible(channel_idx, visible)
        self.channel_visibility_changed.emit(channel_idx, visible)
    
    def _on_channel_opacity_changed(self, channel_idx: int, value: int, label: QtWidgets.QLabel = None) -> None:
        """Handle opacity slider change."""
        if self._updating_ui:
            return
        opacity = float(value) / 100.0
        if self.settings:
            self.settings.set_channel_opacity(channel_idx, opacity)
        
        # Update label
        if label:
            label.setText(f"{opacity*100:.0f}%")
        elif hasattr(self, '_channel_widgets') and channel_idx in self._channel_widgets:
            opacity_label = self._channel_widgets[channel_idx].get('opacity_label')
            if opacity_label:
                opacity_label.setText(f"{opacity*100:.0f}%")
        
        self.channel_opacity_changed.emit(channel_idx, opacity)
    
    def _on_channel_lut_changed(self, channel_idx: int, lut_idx: int) -> None:
        """Handle LUT dropdown change."""
        if self._updating_ui:
            return
        lut_idx = max(0, min(lut_idx, len(LUTS) - 1))
        if self.settings:
            self.settings.set_channel_lut(channel_idx, lut_idx)
        self.channel_lut_changed.emit(channel_idx, lut_idx)
    
    def _on_blend_mode_changed(self, index: int) -> None:
        """Handle blend mode combo change."""
        if self._updating_ui:
            return
        blend_mode = self.blend_combo.itemData(index)
        if blend_mode and self.settings:
            try:
                self.settings.blend_mode = BlendMode(blend_mode)
            except ValueError:
                self.settings.blend_mode = BlendMode.NORMAL
        self.blend_mode_changed.emit(blend_mode or "normal")
    
    def _on_reset_all(self) -> None:
        """Reset all channels to default state."""
        if self.settings is None:
            return
        
        for ch in self.settings.channels:
            ch.visible = True
            ch.opacity = 1.0
            ch.lut = ch.channel_idx % len(LUTS)
        
        self.settings.blend_mode = BlendMode.NORMAL
        self._populate_channels()
        
        # Emit signals for all channels
        for ch in self.settings.channels:
            self.channel_visibility_changed.emit(ch.channel_idx, True)
            self.channel_opacity_changed.emit(ch.channel_idx, 1.0)
            self.channel_lut_changed.emit(ch.channel_idx, ch.lut)
        self.blend_mode_changed.emit("normal")
