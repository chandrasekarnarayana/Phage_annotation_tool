"""Preferences dialog and settings-change handlers."""

from __future__ import annotations

from matplotlib.backends.qt_compat import QtWidgets

from phage_annotator.ui_qt.rendering.lut_manager import lut_names
from phage_annotator.ui_qt.services.panel_logging import get_panel_logger


from phage_annotator.ui_qt.controls.preferences_controls_mixin_methods1 import _PreferencesControlsMixinMethods1
from phage_annotator.ui_qt.controls.preferences_controls_mixin_methods2 import _PreferencesControlsMixinMethods2

class PreferencesControlsMixin(_PreferencesControlsMixinMethods1, _PreferencesControlsMixinMethods2):
    """Mixin for preferences and configuration handlers."""

    pass
