"""Tooltip and event-filter helpers for the main window."""

from __future__ import annotations

import logging

from matplotlib.backends.qt_compat import QtCore, QtWidgets


logger = logging.getLogger(__name__)


class UiTooltipMixin:
    """Mixin for delayed tooltips and tooltip cleanup."""

    def _install_delayed_micro_help(self, widget: QtWidgets.QWidget, text: str) -> None:
        """Register long-hover micro-help bubble (quiet, delayed)."""
        if widget is None:
            return
        timers = getattr(self, "_micro_help_timers", None)
        if timers is None:
            timers = {}
            self._micro_help_timers = timers
        payload = str(text).strip()
        if not payload:
            return
        if widget in timers:
            timers[widget].stop()
            try:
                timers[widget].deleteLater()
            except Exception:
                logger.debug("Failed to delete existing micro-help timer", exc_info=True)
        timer = QtCore.QTimer(self)
        timer.setSingleShot(True)
        timer.setInterval(850)

        def _show_tip() -> None:
            """Show tip for the current workflow."""
            if widget is None or not widget.isVisible():
                return
            center = widget.rect().center()
            pos = widget.mapToGlobal(center)
            QtWidgets.QToolTip.showText(pos, payload, widget)

        timer.timeout.connect(_show_tip)
        timers[widget] = timer
        widget.installEventFilter(self)

    def eventFilter(self, obj, event) -> bool:  # noqa: N802 - Qt API
        """Drive delayed micro-help display on long-hover."""
        timers = getattr(self, "_micro_help_timers", None)
        if isinstance(timers, dict) and obj in timers:
            ev_type = event.type()
            if ev_type == QtCore.QEvent.Type.Enter:
                timers[obj].start()
            elif ev_type in (
                QtCore.QEvent.Type.Leave,
                QtCore.QEvent.Type.MouseButtonPress,
                QtCore.QEvent.Type.FocusOut,
                QtCore.QEvent.Type.Hide,
            ):
                timers[obj].stop()
                try:
                    QtWidgets.QToolTip.hideText()
                except Exception:
                    logger.debug("Failed to hide tooltip while clearing micro-help", exc_info=True)
        return QtWidgets.QMainWindow.eventFilter(self, obj, event)

    def _clear_all_tooltips(self) -> None:
        """Clear any lingering tooltips from the screen."""
        try:
            QtWidgets.QToolTip.hideText()
        except Exception:
            logger.debug("Failed to hide tooltip during tooltip cleanup", exc_info=True)
        timers = getattr(self, "_micro_help_timers", None)
        if isinstance(timers, dict):
            for timer in timers.values():
                try:
                    timer.stop()
                except Exception:
                    logger.debug("Failed to stop pending micro-help timer", exc_info=True)
