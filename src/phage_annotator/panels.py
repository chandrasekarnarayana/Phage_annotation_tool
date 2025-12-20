"""Panel registry specs for dock creation.

This module defines a lightweight dataclass used to register feature panels.
The registry enables consistent dock creation, default layout resets, and
View menu toggles without duplicating setup code.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Callable, Optional

from matplotlib.backends.qt_compat import QtCore, QtWidgets


@dataclass(frozen=True)
class PanelSpec:
    """Declarative spec for a dockable panel.

    Attributes
    ----------
    id : str
        Stable identifier used for QSettings and command palette labels.
    title : str
        Dock window title.
    default_area : QtCore.Qt.DockWidgetArea
        Default dock area for layout reset.
    default_visible : bool
        Initial visibility for layout reset.
    widget_factory : Callable[[], QtWidgets.QWidget]
        Factory that returns the panel widget (created on demand).
    toggle_action_text : str
        User-facing label for the View menu toggle action.
    shortcut : str, optional
        Optional keyboard shortcut for the toggle action.
    """
    id: str
    title: str
    default_area: QtCore.Qt.DockWidgetArea
    default_visible: bool
    widget_factory: Callable[[], QtWidgets.QWidget]
    toggle_action_text: str
    shortcut: Optional[str] = None


def roi_manager_spec(widget_factory) -> PanelSpec:
    """Helper to build ROI Manager panel spec."""
    return PanelSpec(
        id="roi_manager",
        title="ROI Manager",
        default_area=QtCore.Qt.RightDockWidgetArea,
        default_visible=False,
        widget_factory=widget_factory,
        toggle_action_text="ROI Manager",
    )
