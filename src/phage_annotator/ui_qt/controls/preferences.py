"""Preferences and configuration handlers."""

from __future__ import annotations

from matplotlib.backends.qt_compat import QtWidgets

from phage_annotator.ui_qt.rendering.lut_manager import lut_names
from phage_annotator.ui_qt.services.panel_logging import get_panel_logger


from phage_annotator.ui_qt.controls.preferences_controls_mixin import PreferencesControlsMixin

__all__ = ["PreferencesControlsMixin"]
