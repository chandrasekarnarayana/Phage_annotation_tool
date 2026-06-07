"""UI construction helpers for the main window."""

from __future__ import annotations

from typing import List, Optional, Tuple

from matplotlib.backends.backend_qt5agg import FigureCanvasQTAgg, NavigationToolbar2QT
from matplotlib.backends.qt_compat import QtCore, QtWidgets
from matplotlib.figure import Figure

from phage_annotator.ui_qt.utils import ui_actions, ui_docks
from phage_annotator.ui_qt.utils.ui_setup_registry import UiSetupRegistryMixin
from phage_annotator.ui_qt.utils.ui_setup_assist import build_assist_controls
from phage_annotator.ui_qt.utils.ui_setup_canvas import (
    build_annotation_table_panel,
    build_canvas_workspace,
)
from phage_annotator.ui_qt.utils.ui_setup_panels import (
    build_panel_policy_controls,
    refresh_panel_policy_controls,
)
from phage_annotator.ui_qt.utils.ui_setup_workspace import build_modality_loader_section
from phage_annotator.ui_qt.keyboard_registry import apply_menu_shortcuts
from phage_annotator.ui_qt.utils.constants import DEFAULT_PLAYBACK_FPS
from phage_annotator.ui_qt.panels.registry import PanelSpec
from phage_annotator.ui_qt.rendering.lut_manager import LUTS, cmap_for, lut_names
from phage_annotator.ui_qt.panels.performance import PerformancePanel
from phage_annotator.rendering.mpl import Renderer
from phage_annotator.ui_qt.models.lazy_loader import LAZY_LOADER_TREE_HEADER
from phage_annotator.ui_qt.widgets.modality_canvas import ModalityCanvasManager

try:
    from phage_annotator.ui_qt.utils.bcontrast_integration import integrate_b_contrast_features
    HAS_BCONTRAST = True
except ImportError:
    HAS_BCONTRAST = False

# Temporary feature gates.
DISABLE_QC = True
DISABLE_DIAGNOSTICS = True
DISABLE_SHORTCUTS = False


from phage_annotator.ui_qt.utils.ui_setup_methods1 import _UiSetupMixinMethods1
from phage_annotator.ui_qt.utils.ui_setup_methods2 import _UiSetupMixinMethods2
from phage_annotator.ui_qt.utils.ui_setup_methods3 import _UiSetupMixinMethods3
from phage_annotator.ui_qt.utils.ui_setup_methods4 import _UiSetupMixinMethods4

class UiSetupMixin(_UiSetupMixinMethods1, _UiSetupMixinMethods2, _UiSetupMixinMethods3, _UiSetupMixinMethods4, UiSetupRegistryMixin):
    """Mixin containing UI construction and dock wiring."""

    pass
