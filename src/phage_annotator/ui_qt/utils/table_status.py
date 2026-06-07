"""Annotation table and status bar helpers - aggregator."""
from __future__ import annotations

from phage_annotator.ui_qt.utils.table_status_core import TableStatusCoreMixin
from phage_annotator.ui_qt.utils.table_status_bar import TableStatusBarMixin
from phage_annotator.ui_qt.utils.table_status_events import TableStatusEventsMixin
from phage_annotator.ui_qt.utils.table_status_navigation import TableStatusNavigationMixin
from phage_annotator.ui_qt.utils.table_status_update import TableStatusUpdateMixin


class TableStatusMixin(
    TableStatusCoreMixin,
    TableStatusBarMixin,
    TableStatusEventsMixin,
    TableStatusNavigationMixin,
    TableStatusUpdateMixin,
):
    """Aggregated mixin for annotation table management and status bar updates."""
    pass
