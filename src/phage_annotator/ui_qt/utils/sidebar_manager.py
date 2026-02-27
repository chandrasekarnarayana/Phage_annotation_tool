"""Sidebar layout helpers for canvas-first docking."""

from __future__ import annotations

from dataclasses import dataclass
from typing import List


@dataclass(frozen=True)
class SidebarLayoutConfig:
    """Layout sizing configuration for sidebar and annotations docks."""

    expanded_width: int = 300
    collapsed_width: int = 48
    annotations_width: int = 320


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
    ) -> List[int]:
        """Return dock sizes in sidebar->annotations order."""
        sizes: List[int] = []
        if sidebar_visible:
            sizes.append(self.config.collapsed_width if collapsed else self.config.expanded_width)
        if annotations_visible:
            sizes.append(self.config.annotations_width)
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
