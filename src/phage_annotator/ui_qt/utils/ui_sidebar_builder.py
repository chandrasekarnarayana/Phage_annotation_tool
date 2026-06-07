"""Dock registry and panel-factory helpers for UI setup."""

from __future__ import annotations

from typing import List, Optional, Tuple

from matplotlib.backends.qt_compat import QtWidgets

from phage_annotator.ui_qt.panels.performance import PerformancePanel
from phage_annotator.ui_qt.panels.registry import PanelSpec
from phage_annotator.ui_qt.utils import ui_docks
from phage_annotator.ui_qt.utils.ui_setup_panels import (
    build_panel_policy_controls,
    refresh_panel_policy_controls,
)

from phage_annotator.ui_qt.utils.ui_sidebar_builder_methods1 import _UiSidebarBuilderMixinMethods1
from phage_annotator.ui_qt.utils.ui_sidebar_builder_methods2 import _UiSidebarBuilderMixinMethods2

class UiSidebarBuilderMixin(_UiSidebarBuilderMixinMethods1, _UiSidebarBuilderMixinMethods2):
    """Widget factories and sidebar page construction."""

    pass
