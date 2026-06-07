"""Visual indicators for modality state, sync status, and display settings."""
from __future__ import annotations

from matplotlib.backends.qt_compat import QtCore, QtGui, QtWidgets


class ModalityIndicator(QtWidgets.QWidget):
    """Visual indicator widget for modality state."""

    def __init__(self, parent: QtWidgets.QWidget | None = None):
        """Document the init flow."""
        super().__init__(parent)
        self._modality_name = "Modality 1"
        self._projection_type = "Raw"
        self._is_active = False
        self._is_linked = False
        self.setMinimumHeight(24)
        self.setMinimumWidth(150)

    def set_modality_info(self, name: str, projection_type: str,
                          is_active: bool = False, is_linked: bool = False) -> None:
        """Document the set_modality_info flow."""
        self._modality_name = name
        self._projection_type = projection_type
        self._is_active = is_active
        self._is_linked = is_linked
        self.update()

    def paintEvent(self, event: QtGui.QPaintEvent) -> None:
        """Document the paintEvent flow."""
        painter = QtGui.QPainter(self)
        painter.setRenderHint(QtGui.QPainter.RenderHint.Antialiasing, True)
        if self._is_active:
            bg_color = QtGui.QColor("#e8f4f8")
            border_color = QtGui.QColor("#2c95a8")
            border_width = 2
        else:
            bg_color = QtGui.QColor("#f5f5f5")
            border_color = QtGui.QColor("#cccccc")
            border_width = 1
        painter.fillRect(self.rect(), bg_color)
        painter.setPen(QtGui.QPen(border_color, border_width))
        painter.drawRect(0, 0, self.width() - 1, self.height() - 1)
        painter.setPen(QtGui.QPen(QtGui.QColor("#000000")))
        font = painter.font()
        font.setPointSize(9)
        painter.setFont(font)
        text = f"{self._modality_name} ({self._projection_type})"
        painter.drawText(6, 2, self.width() - 12, self.height() - 4,
                         QtCore.Qt.AlignmentFlag.AlignLeft | QtCore.Qt.AlignmentFlag.AlignVCenter, text)
        if self._is_linked:
            painter.fillRect(QtCore.QRect(self.width() - 18, 5, 13, 13), QtGui.QColor("#4c78a8"))
            painter.setPen(QtGui.QPen(QtGui.QColor("#ffffff"), 1))
            painter.drawText(QtCore.QRect(self.width() - 18, 5, 13, 13),
                             QtCore.Qt.AlignmentFlag.AlignCenter, "L")
        painter.end()

    def sizeHint(self) -> QtCore.QSize:
        """Document the sizeHint flow."""
        return QtCore.QSize(150, 24)


class SyncStateIndicator(QtWidgets.QWidget):
    """Visual indicator for synchronization state."""

    def __init__(self, parent: QtWidgets.QWidget | None = None):
        """Document the init flow."""
        super().__init__(parent)
        self._sync_vmin = False
        self._sync_vmax = False
        self._sync_contrast = False
        self.setMinimumHeight(28)
        self.setMinimumWidth(180)

    def set_sync_state(self, vmin: bool = False, vmax: bool = False,
                       contrast: bool = False, brightness: bool = False) -> None:
        """Document the set_sync_state flow."""
        self._sync_vmin = vmin
        self._sync_vmax = vmax
        self._sync_contrast = contrast
        self.update()

    def paintEvent(self, event: QtGui.QPaintEvent) -> None:
        """Document the paintEvent flow."""
        painter = QtGui.QPainter(self)
        painter.setRenderHint(QtGui.QPainter.RenderHint.Antialiasing, True)
        painter.fillRect(self.rect(), QtGui.QColor("#ffffff"))
        painter.setPen(QtGui.QPen(QtGui.QColor("#ddd"), 1))
        painter.drawRect(0, 0, self.width() - 1, self.height() - 1)
        font = painter.font()
        font.setPointSize(8)
        font.setBold(True)
        painter.setFont(font)
        painter.setPen(QtGui.QPen(QtGui.QColor("#666")))
        painter.drawText(4, 2, 100, 12, QtCore.Qt.AlignmentFlag.AlignLeft, "Sync:")
        x_pos = 45
        sync_items = [("vmin", self._sync_vmin), ("vmax", self._sync_vmax), ("C", self._sync_contrast)]
        for i, (label, is_synced) in enumerate(sync_items):
            color = QtGui.QColor("#4c78a8") if is_synced else QtGui.QColor("#ccc")
            painter.fillRect(QtCore.QRect(x_pos + i * 35, 16, 14, 10), color)
            text_color = QtGui.QColor("#ffffff") if is_synced else QtGui.QColor("#999")
            painter.setPen(QtGui.QPen(text_color))
            painter.drawText(QtCore.QRect(x_pos + i * 35, 16, 14, 10),
                             QtCore.Qt.AlignmentFlag.AlignCenter, label)
        painter.end()

    def sizeHint(self) -> QtCore.QSize:
        """Document the sizeHint flow."""
        return QtCore.QSize(180, 40)


class DisplaySettingsBadge(QtWidgets.QWidget):
    """Compact badge showing active display settings."""

    def __init__(self, parent: QtWidgets.QWidget | None = None):
        """Document the init flow."""
        super().__init__(parent)
        self._mode = "Auto"
        self._is_modified = False
        self.setMinimumHeight(20)
        self.setMinimumWidth(60)

    def set_display_mode(self, mode: str, is_modified: bool = False) -> None:
        """Document the set_display_mode flow."""
        self._mode = mode
        self._is_modified = is_modified
        self.update()

    def paintEvent(self, event: QtGui.QPaintEvent) -> None:
        """Document the paintEvent flow."""
        painter = QtGui.QPainter(self)
        painter.setRenderHint(QtGui.QPainter.RenderHint.Antialiasing, True)
        mode_colors = {
            "Auto": QtGui.QColor("#4c78a8"),
            "Linear": QtGui.QColor("#55a630"),
            "Log": QtGui.QColor("#d97706"),
            "Sqrt": QtGui.QColor("#9333ea"),
        }
        bg_color = mode_colors.get(self._mode, QtGui.QColor("#666"))
        path = QtGui.QPainterPath()
        path.addRoundedRect(QtCore.QRectF(0, 0, self.width(), self.height()), 4, 4)
        painter.fillPath(path, bg_color)
        painter.setPen(QtGui.QPen(QtGui.QColor("#ffffff")))
        font = painter.font()
        font.setPointSize(8)
        font.setBold(True)
        painter.setFont(font)
        text = self._mode + ("*" if self._is_modified else "")
        painter.drawText(self.rect(), QtCore.Qt.AlignmentFlag.AlignCenter, text)
        painter.end()

    def sizeHint(self) -> QtCore.QSize:
        """Document the sizeHint flow."""
        return QtCore.QSize(60, 20)


class StatusIndicatorBar(QtWidgets.QWidget):
    """Compact status bar showing all visual indicators."""

    def __init__(self, parent: QtWidgets.QWidget | None = None):
        """Document the init flow."""
        super().__init__(parent)
        layout = QtWidgets.QHBoxLayout()
        layout.setContentsMargins(4, 2, 4, 2)
        layout.setSpacing(8)
        self.modality_indicator = ModalityIndicator()
        layout.addWidget(self.modality_indicator, 1)
        self.display_badge = DisplaySettingsBadge()
        layout.addWidget(self.display_badge)
        self.sync_indicator = SyncStateIndicator()
        layout.addWidget(self.sync_indicator, 1)
        self.setLayout(layout)
        self.setStyleSheet("QWidget { background-color: #f9f9f9; border-top: 1px solid #ddd; }")

    def update_status(self, modality_name: str = "Modality 1", projection_type: str = "Raw",
                      is_active: bool = False, is_linked: bool = False,
                      display_mode: str = "Auto", is_modified: bool = False,
                      sync_vmin: bool = False, sync_vmax: bool = False,
                      sync_contrast: bool = False) -> None:
        """Document the update_status flow."""
        self.modality_indicator.set_modality_info(modality_name, projection_type, is_active, is_linked)
        self.display_badge.set_display_mode(display_mode, is_modified)
        self.sync_indicator.set_sync_state(sync_vmin, sync_vmax, sync_contrast)
