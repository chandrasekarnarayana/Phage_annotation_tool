"""Panel registry specs for dock creation."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Callable, Literal, Optional, Tuple

from matplotlib.backends.qt_compat import QtCore, QtWidgets


PanelBucket = Literal["inspect", "tools", "plots"]


@dataclass(frozen=True)
class PanelConstraints:
    """Behavior constraints for panel placement and floating."""

    allowed_areas: Optional[Tuple[QtCore.Qt.DockWidgetArea, ...]] = None
    floatable: bool = True
    fixed_area: bool = False


@dataclass(frozen=True)
class PanelSpec:
    """Declarative spec for a dockable panel."""

    id: str
    title: str
    default_area: QtCore.Qt.DockWidgetArea
    default_visible: bool
    widget_factory: Callable[[], QtWidgets.QWidget]
    toggle_action_text: str
    shortcut: Optional[str] = None
    bucket: PanelBucket = "tools"
    tab_group: Optional[str] = None
    constraints: PanelConstraints = PanelConstraints()
    search_aliases: Tuple[str, ...] = ()


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
