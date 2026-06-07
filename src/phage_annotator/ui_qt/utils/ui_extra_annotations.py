"""Annotation-view helpers for the main window."""

from __future__ import annotations

import logging

from matplotlib.backends.qt_compat import QtCore, QtWidgets

from phage_annotator.ui_qt.utils.source_protocols import SourceProtocolsMixin

logger = logging.getLogger(__name__)


class _LogicalVisibilityLabel(QtWidgets.QLabel):
    """QLabel that reports logical visibility even when parent containers are hidden."""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._logical_visible = True

    def setVisible(self, visible: bool) -> None:  # noqa: N802
        self._logical_visible = bool(visible)
        super().setVisible(bool(visible))

    def isVisible(self) -> bool:  # noqa: N802
        if not self._logical_visible:
            return False
        return not self.isHidden()


class UiAnnotationViewsMixin(SourceProtocolsMixin):
    """Mixin for lazy-loader-backed annotation view controls."""
    pass
