"""Panel registry for 10-panel maximum separation UI architecture.

This module defines the declarative registry for sidebar panels,
enabling consistent panel creation, toggle behavior, and layout presets.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Callable, Optional

from matplotlib.backends.qt_compat import QtCore, QtWidgets


@dataclass(frozen=True)
class SidebarPanelSpec:
    """Declarative spec for a sidebar panel in the 10-panel architecture.

    Attributes
    ----------
    id : str
        Stable identifier used for QSettings and persistence (e.g., "explore", "annotate").
    title : str
        User-facing panel title displayed in activity bar tooltips.
    icon : QtWidgets.QStyle.StandardPixmap
        Icon displayed in the activity bar.
    default_visible : bool
        Whether the panel is visible by default (for layout presets).
    widget_builder : Callable[[], QtWidgets.QWidget]
        Factory that returns the panel widget (created on demand).
    menu_action_id : str
        Identifier for the menu action (for View -> Panels menu integration).
    shortcut : str, optional
        Optional keyboard shortcut for quick panel access.
    order : int
        Display order in the activity bar (0-9 for 10 panels).
    """

    id: str
    title: str
    icon: QtWidgets.QStyle.StandardPixmap
    default_visible: bool
    widget_builder: Callable[[], QtWidgets.QWidget]
    menu_action_id: str
    order: int
    shortcut: Optional[str] = None


def build_sidebar_panel_registry(self) -> list[SidebarPanelSpec]:
    """Build the registry of 10 sidebar panels.

    Returns ordered list of panels for activity bar display.
    PLAYBACK is conceptually present but implemented as bottom bar only.
    """

    # Reuse the existing page builder and widget factories from the active UI setup.
    pages = self._build_sidebar_pages(self.display_group)

    # Map the existing pages to SidebarPanelSpec
    registry: list[SidebarPanelSpec] = []

    # The pages are already in order: Explore, Annotate, Display, Playback,
    # ROI/Crop, Analyze, Results, Project, Export, Preferences
    panel_ids = [
        "explore",
        "annotate",
        "display",
        "playback",
        "roi_crop",
        "analyze",
        "results",
        "project",
        "export",
        "preferences",
    ]

    for order, (title, icon, widget) in enumerate(pages):
        panel_id = panel_ids[order] if order < len(panel_ids) else f"panel_{order}"

        # Create a closure that returns the pre-built widget
        def make_widget_factory(w=widget):
            return lambda: w

        spec = SidebarPanelSpec(
            id=panel_id,
            title=title,
            icon=icon,
            default_visible=(order < 3),  # Explore, Annotate, Display visible by default
            widget_builder=make_widget_factory(),
            menu_action_id=f"sidebar_{panel_id}_act",
            order=order,
        )
        registry.append(spec)

        # Set objectName for testability
        widget.setObjectName(f"sidebar_panel_{panel_id}")

    return registry
