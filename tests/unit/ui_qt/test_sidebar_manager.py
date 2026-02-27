"""Unit tests for sidebar layout helpers."""

from __future__ import annotations

from phage_annotator.ui_qt.utils.sidebar_manager import SidebarLayoutConfig, SidebarManager


def test_dock_sizes_expanded_sidebar_and_annotations() -> None:
    manager = SidebarManager(SidebarLayoutConfig(expanded_width=300, collapsed_width=48, annotations_width=320))
    sizes = manager.dock_sizes(sidebar_visible=True, annotations_visible=True, collapsed=False)
    assert sizes == [300, 320]


def test_dock_sizes_collapsed_sidebar_and_annotations() -> None:
    manager = SidebarManager(SidebarLayoutConfig(expanded_width=300, collapsed_width=48, annotations_width=320))
    sizes = manager.dock_sizes(sidebar_visible=True, annotations_visible=True, collapsed=True)
    assert sizes == [48, 320]


def test_dock_sizes_sidebar_only() -> None:
    manager = SidebarManager(SidebarLayoutConfig(expanded_width=280, collapsed_width=40, annotations_width=320))
    sizes = manager.dock_sizes(sidebar_visible=True, annotations_visible=False, collapsed=False)
    assert sizes == [280]


def test_dock_sizes_annotations_only() -> None:
    manager = SidebarManager(SidebarLayoutConfig(expanded_width=280, collapsed_width=40, annotations_width=310))
    sizes = manager.dock_sizes(sidebar_visible=False, annotations_visible=True, collapsed=False)
    assert sizes == [310]


def test_dock_sizes_none_visible() -> None:
    manager = SidebarManager()
    sizes = manager.dock_sizes(sidebar_visible=False, annotations_visible=False, collapsed=False)
    assert sizes == []


def test_dock_order_matches_visibility() -> None:
    manager = SidebarManager()
    order = manager.dock_order(sidebar_visible=True, annotations_visible=True)
    assert order == ["sidebar", "annotations"]


def test_breadcrumb_text() -> None:
    manager = SidebarManager()
    assert manager.breadcrumb_text("Explore") == "Sidebar / Explore"


def test_clamp_index_bounds() -> None:
    manager = SidebarManager()
    assert manager.clamp_index(-5, 4) == 0
    assert manager.clamp_index(10, 4) == 3
    assert manager.clamp_index(2, 4) == 2
