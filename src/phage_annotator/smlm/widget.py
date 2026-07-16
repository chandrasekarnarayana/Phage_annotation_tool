"""Qt widget for ThunderSTORM-style SMLM controls."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Callable, Iterable, Optional

from matplotlib.backends.qt_compat import QtWidgets

from phage_annotator.smlm.context_menu import ContextMenuMixin
from phage_annotator.smlm.dock_widget_handlers import DockWidgetHandlersMixin, SmlmUiValues
from phage_annotator.smlm.dock_widget_ui import DockWidgetUiMixin


class SmlmDockWidget(ContextMenuMixin, DockWidgetHandlersMixin, DockWidgetUiMixin, QtWidgets.QWidget):
    """Parameter panel for the ThunderSTORM-style SMLM localization pipeline.

    Combines UI construction (DockWidgetUiMixin), event handlers
    (DockWidgetHandlersMixin), and context-menu support (ContextMenuMixin).
    The :meth:`values` method returns a typed :class:`SmlmUiValues` snapshot
    for passing to the analysis backend.
    """

    pass
