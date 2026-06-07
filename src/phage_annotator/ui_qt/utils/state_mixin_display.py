"""Extracted method group 5 for StateMixin."""

from __future__ import annotations

import pathlib
from types import MappingProxyType
from typing import Dict, List, Optional, Tuple, TYPE_CHECKING

import numpy as np
from matplotlib.backends.qt_compat import QtCore

from phage_annotator.analysis.core import compute_projection, compute_projections
from phage_annotator.annotation.core import Keypoint, PointSuggestion
from phage_annotator.io.data.calibration import CalibrationState
from phage_annotator.ui_qt.utils.constants import PROJECTION_ASYNC_BYTES, CancelTokenShim
from phage_annotator.ui_qt.utils.debug import debug_log
from phage_annotator.ui_qt.utils.image_io import load_array
from phage_annotator.io import read_contiguous_block
from phage_annotator.data.pyramid import downsample_mean_pool, pyramid_level_factor

if TYPE_CHECKING:
    from phage_annotator.data.models import LazyImage



class StateMixinDisplayMixin:
    """Method group 5 extracted from StateMixin."""

    def _update_buffer_stats(self) -> None:
        """Update playback buffer stats in the status bar."""
        if self.buffer_stats_label is None:
            return
        stats = self._playback_ring.stats()
        block_size = int(self._settings.value("prefetchBlockSizeFrames", 64, type=int))
        self.buffer_stats_label.setText(
            f"Buffer: {stats.filled}/{stats.capacity} | Prefetch: {block_size} | Underruns: {self._playback_underruns}"
        )
    def get_diagnostic_info(self, image_id: int) -> dict:
        """Get detailed diagnostic info for a given image.
        
        Returns
        -------
        dict
            Diagnostic information including:
            - downsampled: bool
            - downsampling_reason: Optional[str]
            - lod_active: bool
            - memmap: bool
            - downsample_factor: int
            - render_scale: float (interactive downsampling factor)
        """
        img = None
        for image in self.images:
            if image.id == image_id:
                img = image
                break
        if img is None:
            return {}
        
        render_scales = getattr(self, "_render_scales", {}) or {}
        render_scale = render_scales.get(image_id, 1.0)
        lod_active = getattr(self, "_lod_mode_active", {}) or {}
        
        return {
            "downsampled": getattr(img, "downsampled", False),
            "downsampling_reason": getattr(img, "downsampling_reason", None),
            "downsample_factor": getattr(img, "downsample_factor", 1),
            "lod_active": lod_active.get(image_id, False),
            "memmap": getattr(img.array, "filename", None) is not None if img.array else False,
            "render_scale": float(render_scale),
        }
    def format_diagnostic_tooltip(self, image_id: int) -> str:
        """Format a detailed diagnostic tooltip for display.
        
        Example output:
        "Image 1: Spatial 2x downsampled (memory: 1.9 GB > 1.5 GB threshold)
         Interactive: 2x downsampled; LOD active; Memmap"
        """
        diags = self.get_diagnostic_info(image_id)
        if not diags:
            return "No diagnostic information"
        
        lines = []
        
        # Memory pressure diagnostics
        if diags["downsampled"]:
            reason = diags.get("downsampling_reason", "")
            lines.append(f"Spatial downsampling: {diags['downsample_factor']}x")
            if reason:
                lines.append(f"  Reason: {reason}")
        
        # Interactive/render diagnostics
        interactive_flags = []
        if diags["render_scale"] > 1:
            interactive_flags.append(f"Interactive {int(diags['render_scale'])}x")
        if diags["lod_active"]:
            interactive_flags.append("LOD active")
        if diags["memmap"]:
            interactive_flags.append("Memmap mode")
        
        if interactive_flags:
            lines.append("Display: " + "; ".join(interactive_flags))
        
        return "\n".join(lines) if lines else "Full resolution, no optimizations active"
    def _flash_status(self, text: str, ms: int = 1200) -> None:
        """Show a temporary status message without overwriting derived status."""
        status_service = getattr(self, "status_service", None)
        if status_service is None:
            return
        from phage_annotator.ui_qt.services.status import StatusMessage

        status_service.post_message(
            StatusMessage(
                text=str(text),
                severity=status_service.infer_severity(text),
                timeout_ms=int(ms),
                source="legacy._flash_status",
                sticky=False,
                min_visible_ms=min(int(ms), 1200),
            )
        )
    def _status_info(self, text: str, *, timeout_ms: int | None = None, source: str = "ui") -> None:
        """Post an informational status message through the centralized service."""
        status_service = getattr(self, "status_service", None)
        if status_service is None:
            return
        status_service.info(text, timeout_ms=timeout_ms, source=source)
    def _status_success(self, text: str, *, timeout_ms: int | None = None, source: str = "ui") -> None:
        """Post a success status message through the centralized service."""
        status_service = getattr(self, "status_service", None)
        if status_service is None:
            return
        status_service.success(text, timeout_ms=timeout_ms, source=source)
    def _status_warning(
        self,
        text: str,
        *,
        timeout_ms: int | None = None,
        source: str = "ui",
        sticky: bool = False,
    ) -> None:
        """Post a warning status message through the centralized service."""
        status_service = getattr(self, "status_service", None)
        if status_service is None:
            return
        status_service.warning(text, timeout_ms=timeout_ms, source=source, sticky=sticky)
    def _status_error(
        self,
        text: str,
        *,
        timeout_ms: int | None = None,
        source: str = "ui",
        sticky: bool = False,
    ) -> None:
        """Post an error status message through the centralized service."""
        status_service = getattr(self, "status_service", None)
        if status_service is None:
            return
        status_service.error(text, timeout_ms=timeout_ms, source=source, sticky=sticky)
