"""Extracted method group 1 for UiSetupMixin."""

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



class UiSetupBaseMixin:
    """Method group 1 extracted from UiSetupMixin."""

    def _has_canvas_rows(self) -> bool:
        """Return True when modality rows exist for canvas rendering."""
        controller = getattr(self, "controller", None)
        if controller is None:
            return False
        manager = getattr(controller.session_state, "modality_manager", None)
        if manager is None:
            return False
        return bool(manager.get_all_modalities())
