"""Feature panels for the GUI application."""

# Re-export panel classes for backward compatibility during migration
from phage_annotator.ui_qt.panels.channel_controls import ChannelControlPanel

__all__ = [
    "ThresholdPanel",
    "DensityPanel",
    "PerformancePanel",
    "ChannelControlPanel",
]
