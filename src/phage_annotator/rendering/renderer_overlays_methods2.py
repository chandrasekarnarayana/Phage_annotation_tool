"""Method group 2 split from renderer_overlays.py."""

from __future__ import annotations

# Unified logging through service framework
try:
    from phage_annotator.framework import get_log_service
    _logger = get_log_service().get_logger(__name__)
except (ImportError, RuntimeError, AttributeError):
    import logging
    _logger = logging.getLogger(__name__)

from typing import Dict, List, Optional, Tuple

import matplotlib
import matplotlib.pyplot as plt
import numpy as np

from phage_annotator.roi.interactor import CircleROI, RectROI
from phage_annotator.rendering.mpl_canvas import RenderContext
from phage_annotator.rendering.mpl_utils import _clear_overlays


class _RendererOverlaysMixinMethods2:
    """Methods split from RendererOverlaysMixin."""

    def _update_scalebar(self, ctx: RenderContext) -> None:
        """Update scalebar for the current workflow."""
        ax = self.axes.get(ctx.primary_panel) or next(iter(self.axes.values()), None)
        if ax is None:
            return
        if ctx.scale_bar_warning:
            if self.scale_bar_warning is None:
                self.scale_bar_warning = ax.text(
                    0.01,
                    0.02,
                    "",
                    transform=ax.transAxes,
                    ha="left",
                    va="bottom",
                    fontsize=8,
                    color="white",
                    bbox=dict(
                        boxstyle="round,pad=0.2",
                        facecolor="black",
                        alpha=0.35,
                        edgecolor="none",
                    ),
                )
                self.scale_bar_warning.set_gid("scalebar")
            self.scale_bar_warning.set_text(ctx.scale_bar_warning)
            self.scale_bar_warning.set_visible(True)
        elif self.scale_bar_warning is not None:
            self.scale_bar_warning.set_visible(False)
        if not ctx.scale_bar:
            if self.scale_bar_patch is not None:
                self.scale_bar_patch.set_visible(False)
            if self.scale_bar_text is not None:
                self.scale_bar_text.set_visible(False)
            return
        rect = ctx.scale_bar.get("rect")
        text = ctx.scale_bar.get("text")
        text_pos = ctx.scale_bar.get("text_pos")
        background = ctx.scale_bar.get("background_box", True)
        if rect:
            if self.scale_bar_patch is None:
                self.scale_bar_patch = plt.Rectangle(
                    (rect[0], rect[1]),
                    rect[2],
                    rect[3],
                    color="white",
                    linewidth=0,
                    alpha=0.9,
                )
                self.scale_bar_patch.set_gid("scalebar")
                ax.add_patch(self.scale_bar_patch)
            else:
                self.scale_bar_patch.set_xy((rect[0], rect[1]))
                self.scale_bar_patch.set_width(rect[2])
                self.scale_bar_patch.set_height(rect[3])
            self.scale_bar_patch.set_visible(True)
        if text and text_pos:
            if self.scale_bar_text is None:
                self.scale_bar_text = ax.text(
                    text_pos[0],
                    text_pos[1],
                    text,
                    ha="center",
                    va="bottom",
                    fontsize=8,
                    color="white",
                )
                self.scale_bar_text.set_gid("scalebar")
            else:
                self.scale_bar_text.set_position(text_pos)
                self.scale_bar_text.set_text(text)
            if background:
                self.scale_bar_text.set_bbox(
                    dict(
                        boxstyle="round,pad=0.2",
                        facecolor="black",
                        alpha=0.35,
                        edgecolor="none",
                    )
                )
            else:
                self.scale_bar_text.set_bbox(None)
            self.scale_bar_text.set_visible(True)
