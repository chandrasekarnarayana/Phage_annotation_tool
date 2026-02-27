"""Per-channel display settings for multi-channel image viewing.

This module extends the base display mapping system to support independent
per-channel visibility, opacity, LUT, and blend mode control.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Dict, List, Optional


class BlendMode(Enum):
    """Blend modes for compositing multiple channels."""
    NORMAL = "normal"          # Standard alpha blending
    OVERLAY = "overlay"        # Overlay mode
    SCREEN = "screen"          # Screen (additive) blending
    MULTIPLY = "multiply"      # Multiply blending
    ADD = "add"                # Direct addition
    SUBTRACT = "subtract"      # Subtraction


BLEND_MODE_NAMES = {
    BlendMode.NORMAL: "Normal",
    BlendMode.OVERLAY: "Overlay",
    BlendMode.SCREEN: "Screen",
    BlendMode.MULTIPLY: "Multiply",
    BlendMode.ADD: "Add",
    BlendMode.SUBTRACT: "Subtract",
}


@dataclass
class ChannelDisplayState:
    """Display state for a single channel.
    
    Parameters
    ----------
    channel_idx : int
        Channel index (0-based).
    visible : bool
        Whether channel is displayed.
    opacity : float
        Alpha transparency (0.0 = invisible, 1.0 = fully opaque).
    lut : int
        Colormap/LUT index for this channel.
    """
    
    channel_idx: int
    visible: bool = True
    opacity: float = 1.0
    lut: int = 0
    
    def to_dict(self) -> dict:
        """Serialize to dictionary."""
        return {
            "channel_idx": self.channel_idx,
            "visible": self.visible,
            "opacity": float(self.opacity),
            "lut": int(self.lut),
        }
    
    @classmethod
    def from_dict(cls, data: dict) -> ChannelDisplayState:
        """Deserialize from dictionary."""
        return cls(
            channel_idx=int(data.get("channel_idx", 0)),
            visible=bool(data.get("visible", True)),
            opacity=float(data.get("opacity", 1.0)),
            lut=int(data.get("lut", 0)),
        )


@dataclass
class MultiChannelDisplaySettings:
    """Container for multi-channel display state.
    
    Extends per-modality display settings to support multiple channels
    with independent visibility, opacity, and LUT control.
    
    Parameters
    ----------
    channel_count : int
        Total number of channels in the image.
    channels : List[ChannelDisplayState]
        Per-channel display state (one entry per channel).
    blend_mode : BlendMode
        How to composite multiple channels.
    """
    
    channel_count: int
    channels: List[ChannelDisplayState] = field(default_factory=list)
    blend_mode: BlendMode = BlendMode.NORMAL
    
    def __post_init__(self):
        """Initialize channel states if not provided."""
        if not self.channels:
            self.channels = [
                ChannelDisplayState(channel_idx=i, visible=True, opacity=1.0, lut=i % 6)
                for i in range(self.channel_count)
            ]
    
    def get_channel_state(self, channel_idx: int) -> Optional[ChannelDisplayState]:
        """Get display state for a specific channel."""
        if 0 <= channel_idx < len(self.channels):
            return self.channels[channel_idx]
        return None
    
    def set_channel_visible(self, channel_idx: int, visible: bool) -> None:
        """Set channel visibility."""
        if 0 <= channel_idx < len(self.channels):
            self.channels[channel_idx].visible = visible
    
    def set_channel_opacity(self, channel_idx: int, opacity: float) -> None:
        """Set channel opacity (0.0 to 1.0)."""
        opacity = max(0.0, min(1.0, float(opacity)))
        if 0 <= channel_idx < len(self.channels):
            self.channels[channel_idx].opacity = opacity
    
    def set_channel_lut(self, channel_idx: int, lut: int) -> None:
        """Set channel LUT index."""
        if 0 <= channel_idx < len(self.channels):
            self.channels[channel_idx].lut = max(0, int(lut))
    
    def to_dict(self) -> dict:
        """Serialize to dictionary."""
        return {
            "channel_count": self.channel_count,
            "channels": [ch.to_dict() for ch in self.channels],
            "blend_mode": self.blend_mode.value,
        }
    
    @classmethod
    def from_dict(cls, data: dict) -> MultiChannelDisplaySettings:
        """Deserialize from dictionary."""
        channel_count = int(data.get("channel_count", 1))
        channels_data = data.get("channels", [])
        channels = [ChannelDisplayState.from_dict(ch) for ch in channels_data]
        
        blend_mode_str = data.get("blend_mode", "normal")
        try:
            blend_mode = BlendMode(blend_mode_str)
        except ValueError:
            blend_mode = BlendMode.NORMAL
        
        return cls(
            channel_count=channel_count,
            channels=channels,
            blend_mode=blend_mode,
        )
    
    def get_visible_channels(self) -> List[int]:
        """Get list of visible channel indices."""
        return [
            ch.channel_idx for ch in self.channels if ch.visible
        ]
