"""Sidebar layout helpers for canvas-first docking."""

from __future__ import annotations

from dataclasses import dataclass
from typing import List


@dataclass(frozen=True)
class SidebarLayoutConfig:
    """Layout sizing configuration for left and right sidebars (dock panels).
    
    Both sidebars support expand/collapse toggling:
    - Left sidebar: 300px expanded, 48px collapsed (icon-only)
    - Right sidebar (annotations): 320px expanded, 48px collapsed (icon-only)
    """

    # Left sidebar (tools) sizing
    expanded_width: int = 300
    collapsed_width: int = 48
    
    # Right sidebar (annotations/inspect) sizing
    annotations_width: int = 320                  # Expanded width
    annotations_collapsed_width: int = 48         # Collapsed width (icon-only, matching left)


class SidebarManager:
    """Compute layout sizes and labels for the sidebar experience."""

    def __init__(self, config: SidebarLayoutConfig | None = None) -> None:
        self.config = config or SidebarLayoutConfig()

    def dock_sizes(
        self,
        *,
        sidebar_visible: bool,
        annotations_visible: bool,
        collapsed: bool,
        annotations_collapsed: bool = False,
    ) -> List[int]:
        """Return dock sizes in sidebar->annotations order.
        
        Parameters
        ----------
        sidebar_visible : bool
            Whether left sidebar is visible.
        annotations_visible : bool
            Whether right sidebar is visible.
        collapsed : bool
            Whether left sidebar is in collapsed (icon-only) state.
        annotations_collapsed : bool, optional
            Whether right sidebar is in collapsed (icon-only) state. Default False.
        """
        sizes: List[int] = []
        if sidebar_visible:
            sizes.append(self.config.collapsed_width if collapsed else self.config.expanded_width)
        if annotations_visible:
            sizes.append(
                self.config.annotations_collapsed_width if annotations_collapsed 
                else self.config.annotations_width
            )
        return sizes

    def dock_order(self, sidebar_visible: bool, annotations_visible: bool) -> List[str]:
        """Return the dock order used by dock_sizes()."""
        order: List[str] = []
        if sidebar_visible:
            order.append("sidebar")
        if annotations_visible:
            order.append("annotations")
        return order

    def breadcrumb_text(self, label: str) -> str:
        """Return the sidebar breadcrumb text for a given page label."""
        if not label:
            return "Sidebar"
        return f"Sidebar / {label}"

    def clamp_index(self, idx: int, total: int) -> int:
        """Clamp sidebar index to a valid range."""
        if total <= 0:
            return 0
        return max(0, min(idx, total - 1))
