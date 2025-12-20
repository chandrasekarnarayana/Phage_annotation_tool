"""Orthogonal (XZ/YZ) slice views for Z stacks.

This widget renders XZ and YZ slices from a (Z, Y, X) volume using
Matplotlib. It is designed for lightweight, on-demand updates: the caller
supplies already-sliced arrays and display mapping (norm/cmap), while this
widget handles crosshair overlays and click-to-navigate callbacks.
"""

from __future__ import annotations

import time
from typing import Callable, Optional, Tuple

import numpy as np
from matplotlib.backends.backend_qt5agg import FigureCanvasQTAgg
from matplotlib.backends.qt_compat import QtWidgets
import matplotlib.pyplot as plt


class OrthoViewWidget(QtWidgets.QWidget):
    """XZ/YZ orthogonal viewer with crosshair overlays and click callbacks."""

    def __init__(self, parent: Optional[QtWidgets.QWidget] = None) -> None:
        super().__init__(parent)
        self._last_update = 0.0
        self._downsample = 1
        self._dims: Tuple[int, int, int] = (0, 0, 0)
        self._on_xz_click: Optional[Callable[[int, int], None]] = None
        self._on_yz_click: Optional[Callable[[int, int], None]] = None
        self._message_text_xz = None
        self._message_text_yz = None

        self.fig, (self.ax_xz, self.ax_yz) = plt.subplots(1, 2, figsize=(5, 3))
        self.canvas = FigureCanvasQTAgg(self.fig)
        self.ax_xz.set_title("XZ")
        self.ax_yz.set_title("YZ")
        self.ax_xz.set_xlabel("X")
        self.ax_xz.set_ylabel("Z")
        self.ax_yz.set_xlabel("Y")
        self.ax_yz.set_ylabel("Z")
        self.ax_xz.set_aspect("auto")
        self.ax_yz.set_aspect("auto")
        self.im_xz = None
        self.im_yz = None
        self.xz_hline = self.ax_xz.axhline(0, color="yellow", lw=0.8)
        self.xz_vline = self.ax_xz.axvline(0, color="yellow", lw=0.8)
        self.yz_hline = self.ax_yz.axhline(0, color="yellow", lw=0.8)
        self.yz_vline = self.ax_yz.axvline(0, color="yellow", lw=0.8)
        self.canvas.mpl_connect("button_press_event", self._on_click)

        layout = QtWidgets.QVBoxLayout(self)
        layout.setContentsMargins(8, 8, 8, 8)
        layout.setSpacing(6)
        layout.addWidget(self.canvas)

    def set_callbacks(
        self,
        on_xz_click: Optional[Callable[[int, int], None]] = None,
        on_yz_click: Optional[Callable[[int, int], None]] = None,
    ) -> None:
        """Register callbacks for click navigation events."""
        self._on_xz_click = on_xz_click
        self._on_yz_click = on_yz_click

    def update_views(
        self,
        xz: Optional[np.ndarray],
        yz: Optional[np.ndarray],
        cursor_xy: Tuple[float, float],
        z_index: int,
        dims: Tuple[int, int, int],
        downsample: int,
        norm,
        cmap,
        throttle_ms: Optional[int] = None,
        message: Optional[str] = None,
    ) -> None:
        """Update orthogonal slices and crosshair overlays."""
        now = time.monotonic()
        if throttle_ms is not None and (now - self._last_update) * 1000 < throttle_ms:
            return
        self._last_update = now
        self._downsample = max(1, int(downsample))
        self._dims = dims

        if xz is None or yz is None:
            self._set_message(message or "No Z axis available.")
            return

        self._clear_message()
        self.im_xz = _update_or_create(self.ax_xz, self.im_xz, xz, norm=norm, cmap=cmap)
        self.im_yz = _update_or_create(self.ax_yz, self.im_yz, yz, norm=norm, cmap=cmap)
        self.ax_xz.set_xlim(0, xz.shape[1])
        self.ax_xz.set_ylim(xz.shape[0], 0)
        self.ax_yz.set_xlim(0, yz.shape[1])
        self.ax_yz.set_ylim(yz.shape[0], 0)

        x_full, y_full = cursor_xy
        scale = float(self._downsample)
        x_disp = x_full / scale
        y_disp = y_full / scale
        z_disp = z_index / scale
        self.xz_vline.set_xdata([x_disp, x_disp])
        self.xz_hline.set_ydata([z_disp, z_disp])
        self.yz_vline.set_xdata([y_disp, y_disp])
        self.yz_hline.set_ydata([z_disp, z_disp])
        for line in (self.xz_vline, self.xz_hline, self.yz_vline, self.yz_hline):
            line.set_visible(True)
        self.canvas.draw_idle()

    def _set_message(self, text: str) -> None:
        for line in (self.xz_vline, self.xz_hline, self.yz_vline, self.yz_hline):
            line.set_visible(False)
        if self._message_text_xz is None:
            self._message_text_xz = self.ax_xz.text(
                0.5,
                0.5,
                "",
                transform=self.ax_xz.transAxes,
                ha="center",
                va="center",
                fontsize=9,
                color="gray",
            )
        if self._message_text_yz is None:
            self._message_text_yz = self.ax_yz.text(
                0.5,
                0.5,
                "",
                transform=self.ax_yz.transAxes,
                ha="center",
                va="center",
                fontsize=9,
                color="gray",
            )
        self._message_text_xz.set_text(text)
        self._message_text_yz.set_text(text)
        self.canvas.draw_idle()

    def _clear_message(self) -> None:
        if self._message_text_xz is not None:
            self._message_text_xz.set_text("")
        if self._message_text_yz is not None:
            self._message_text_yz.set_text("")

    def _on_click(self, event) -> None:
        if event.button != 1 or event.xdata is None or event.ydata is None:
            return
        if self._downsample <= 0:
            return
        if event.inaxes is self.ax_xz and self._on_xz_click is not None:
            x = int(round(event.xdata * self._downsample))
            z = int(round(event.ydata * self._downsample))
            x = max(0, min(self._dims[2] - 1, x))
            z = max(0, min(self._dims[0] - 1, z))
            self._on_xz_click(x, z)
        elif event.inaxes is self.ax_yz and self._on_yz_click is not None:
            y = int(round(event.xdata * self._downsample))
            z = int(round(event.ydata * self._downsample))
            y = max(0, min(self._dims[1] - 1, y))
            z = max(0, min(self._dims[0] - 1, z))
            self._on_yz_click(y, z)


def _update_or_create(ax, artist, data: np.ndarray, norm, cmap):
    if artist is None:
        return ax.imshow(data, norm=norm, cmap=cmap, extent=(0, data.shape[1], data.shape[0], 0))
    artist.set_data(data)
    artist.set_norm(norm)
    artist.set_cmap(cmap)
    artist.set_extent((0, data.shape[1], data.shape[0], 0))
    return artist
