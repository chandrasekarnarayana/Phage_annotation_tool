"""Dual-handle slider widget for selecting a numeric range."""

from __future__ import annotations

from typing import Optional, Tuple

from matplotlib.backends.qt_compat import QtCore, QtGui, QtWidgets


class SliderPanelDouble(QtWidgets.QWidget):
    """Dual-handle slider for selecting a min/max range."""

    minChanged = QtCore.pyqtSignal(float)
    maxChanged = QtCore.pyqtSignal(float)
    rangeChanged = QtCore.pyqtSignal(float, float)

    def __init__(
        self,
        parent: Optional[QtWidgets.QWidget] = None,
        *,
        min_val: float = 0.0,
        max_val: float = 1.0,
    ) -> None:
        """Initialize the object and prepare its runtime state."""
        super().__init__(parent)
        self._range_min = float(min_val)
        self._range_max = float(max_val)
        self._min_value = float(min_val)
        self._max_value = float(max_val)
        self._step = 0.0
        self._active_handle: Optional[str] = None
        self.setFocusPolicy(QtCore.Qt.FocusPolicy.StrongFocus)
        self.setMinimumHeight(24)

    def setRange(self, min_val: float, max_val: float) -> None:
        """Set the allowed range for the slider."""
        min_val = float(min_val)
        max_val = float(max_val)
        if max_val < min_val:
            min_val, max_val = max_val, min_val
        self._range_min = min_val
        self._range_max = max_val
        self.setValues(self._min_value, self._max_value, emit_signal=False)

    def setStep(self, step: float) -> None:
        """Set the slider step for keyboard and mouse adjustments."""
        self._step = max(0.0, float(step))

    def setValues(self, min_val: float, max_val: float, *, emit_signal: bool = True) -> None:
        """Set current min/max values and optionally emit signals."""
        min_val = float(min_val)
        max_val = float(max_val)
        if max_val < min_val:
            min_val, max_val = max_val, min_val
        min_val = max(self._range_min, min_val)
        max_val = min(self._range_max, max_val)
        if self._step > 0:
            min_val = self._quantize(min_val)
            max_val = self._quantize(max_val)
        changed = (min_val != self._min_value) or (max_val != self._max_value)
        self._min_value = min_val
        self._max_value = max_val
        if emit_signal and changed:
            self.minChanged.emit(self._min_value)
            self.maxChanged.emit(self._max_value)
            self.rangeChanged.emit(self._min_value, self._max_value)
        self.update()

    def values(self) -> Tuple[float, float]:
        """Return the current min/max values."""
        return self._min_value, self._max_value

    def _quantize(self, value: float) -> float:
        """Handle the quantize helper flow."""
        step = self._step
        if step <= 0:
            return value
        return round((value - self._range_min) / step) * step + self._range_min

    def _value_from_pos(self, x: int) -> float:
        """Handle the value from pos helper flow."""
        rect = self._track_rect()
        if rect.width() <= 0:
            return self._range_min
        ratio = (x - rect.left()) / rect.width()
        ratio = max(0.0, min(1.0, ratio))
        return self._range_min + ratio * (self._range_max - self._range_min)

    def _pos_from_value(self, value: float) -> int:
        """Handle the pos from value helper flow."""
        rect = self._track_rect()
        if self._range_max <= self._range_min:
            return rect.left()
        ratio = (value - self._range_min) / (self._range_max - self._range_min)
        ratio = max(0.0, min(1.0, ratio))
        return int(round(rect.left() + ratio * rect.width()))

    def _track_rect(self) -> QtCore.QRect:
        """Handle the track rect helper flow."""
        padding = 8
        return QtCore.QRect(padding, 8, max(1, self.width() - 2 * padding), 8)

    def _handle_hit(self, pos: QtCore.QPoint, handle_x: int) -> bool:
        """Check if mouse position hits a handle."""
        return abs(pos.x() - handle_x) <= 6

    def mousePressEvent(self, event: QtGui.QMouseEvent) -> None:
        """Handle mouse press - select active handle."""
        pos = event.pos()
        min_x = self._pos_from_value(self._min_value)
        max_x = self._pos_from_value(self._max_value)
        if self._handle_hit(pos, min_x):
            self._active_handle = "min"
        elif self._handle_hit(pos, max_x):
            self._active_handle = "max"
        else:
            if abs(pos.x() - min_x) <= abs(pos.x() - max_x):
                self._active_handle = "min"
            else:
                self._active_handle = "max"
        self._update_from_pos(pos.x())
        super().mousePressEvent(event)

    def mouseMoveEvent(self, event: QtGui.QMouseEvent) -> None:
        """Handle mouse move - update active handle position."""
        if self._active_handle is None:
            return
        self._update_from_pos(event.pos().x())
        super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event: QtGui.QMouseEvent) -> None:
        """Handle mouse release - deselect active handle."""
        self._active_handle = None
        super().mouseReleaseEvent(event)

    def keyPressEvent(self, event: QtGui.QKeyEvent) -> None:
        """Run the keyPressEvent workflow."""
        step = self._step if self._step > 0 else (self._range_max - self._range_min) / 100.0
        if step <= 0:
            return
        delta = 0.0
        if event.key() in (QtCore.Qt.Key.Key_Left, QtCore.Qt.Key.Key_Down):
            delta = -step
        elif event.key() in (QtCore.Qt.Key.Key_Right, QtCore.Qt.Key.Key_Up):
            delta = step
        if delta == 0.0:
            return
        handle = self._active_handle or "min"
        if handle == "min":
            self.setValues(self._min_value + delta, self._max_value)
        else:
            self.setValues(self._min_value, self._max_value + delta)

    def _update_from_pos(self, x: int) -> None:
        """Update slider values based on mouse position."""
        value = self._value_from_pos(x)
        if self._active_handle == "max":
            self.setValues(self._min_value, max(value, self._min_value))
        else:
            self.setValues(min(value, self._max_value), self._max_value)

    def paintEvent(self, event: QtGui.QPaintEvent) -> None:
        """Run the paintEvent workflow."""
        painter = QtGui.QPainter(self)
        painter.setRenderHint(QtGui.QPainter.RenderHint.Antialiasing, True)
        rect = self._track_rect()
        min_x = self._pos_from_value(self._min_value)
        max_x = self._pos_from_value(self._max_value)

        track_color = QtGui.QColor("#d0d0d0")
        range_color = QtGui.QColor("#4c78a8")
        handle_color = QtGui.QColor("#1f1f1f")

        painter.setPen(QtCore.Qt.PenStyle.NoPen)
        painter.setBrush(track_color)
        painter.drawRoundedRect(rect, 4, 4)

        range_rect = QtCore.QRect(min_x, rect.top(), max(1, max_x - min_x), rect.height())
        painter.setBrush(range_color)
        painter.drawRoundedRect(range_rect, 4, 4)

        painter.setBrush(handle_color)
        painter.setPen(QtGui.QPen(QtGui.QColor("#ffffff"), 1))
        painter.drawEllipse(QtCore.QPoint(min_x, rect.center().y()), 6, 6)
        painter.drawEllipse(QtCore.QPoint(max_x, rect.center().y()), 6, 6)

        painter.end()
