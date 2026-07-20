"""UI helpers for sidebar, tool routing, layout, and command palette - aggregator."""
from __future__ import annotations

from phage_annotator.ui_qt.utils.tool_routing import ToolRoutingMixin
from phage_annotator.ui_qt.utils.command_palette import CommandPaletteMixin
from phage_annotator.ui_qt.utils.annotate_panel import AnnotatePanelMixin
from phage_annotator.ui_qt.utils.extras_annotate_panel import ExtrasAnnotatePanelMixin
from phage_annotator.ui_qt.utils.extras_command_palette import ExtrasCommandPaletteMixin
from phage_annotator.ui_qt.utils.extras_lazy_modality import ExtrasLazyModalityMixin
from phage_annotator.ui_qt.utils.extras_lazy_table import ExtrasLazyTableMixin
from phage_annotator.ui_qt.utils.extras_lazy_tree import ExtrasLazyTreeMixin
from phage_annotator.ui_qt.utils.extras_sidebar_toggle import ExtrasSidebarToggleMixin
from phage_annotator.ui_qt.utils.layout_preset import LayoutPresetMixin
from phage_annotator.ui_qt.utils.lazy_annotations import LazyAnnotationsMixin
from phage_annotator.ui_qt.utils.lazy_annotation_table import LazyAnnotationTableMixin
from phage_annotator.ui_qt.utils.lazy_loader_callbacks import LazyLoaderCallbacksMixin
from phage_annotator.ui_qt.utils.lazy_loader_ops import LazyLoaderOpsMixin
from phage_annotator.ui_qt.utils.lazy_loader_state import LazyLoaderStateMixin
from phage_annotator.ui_qt.utils.sidebar_layout import SidebarLayoutMixin
from phage_annotator.ui_qt.utils.sidebar_toolbar import SidebarToolbarMixin
from phage_annotator.ui_qt.utils.ui_extra_refresh import UiRefreshMixin
from phage_annotator.ui_qt.utils.ui_extra_tooltips import UiTooltipMixin
from phage_annotator.ui_qt.utils.ui_extra_annotations import UiAnnotationViewsMixin


class UiExtrasMixin(
    ToolRoutingMixin,
    CommandPaletteMixin,
    AnnotatePanelMixin,
    ExtrasAnnotatePanelMixin,
    ExtrasCommandPaletteMixin,
    ExtrasLazyModalityMixin,
    ExtrasLazyTableMixin,
    ExtrasLazyTreeMixin,
    ExtrasSidebarToggleMixin,
    LayoutPresetMixin,
    LazyAnnotationsMixin,
    LazyAnnotationTableMixin,
    LazyLoaderCallbacksMixin,
    LazyLoaderOpsMixin,
    LazyLoaderStateMixin,
    SidebarLayoutMixin,
    SidebarToolbarMixin,
    UiRefreshMixin,
    UiTooltipMixin,
    UiAnnotationViewsMixin,
):
    """Aggregated mixin for UI sidebar, tool routing, layout, and command palette helpers."""
    pass
