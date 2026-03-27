"""Queued UI refresh helpers for the main window."""

from __future__ import annotations

import logging


logger = logging.getLogger(__name__)


class UiRefreshMixin:
    """Mixin for coalesced GUI refresh scheduling."""

    def _request_ui_refresh(
        self,
        reason: str,
        *,
        image: bool = True,
        table: bool = False,
        status: bool = True,
        metadata: bool = False,
    ) -> None:
        """Queue a coalesced GUI refresh on the Qt event loop."""
        flags = dict(getattr(self, "_ui_refresh_flags", {}) or {})
        flags["image"] = bool(flags.get("image", False) or image)
        flags["table"] = bool(flags.get("table", False) or table)
        flags["status"] = bool(flags.get("status", False) or status)
        flags["metadata"] = bool(flags.get("metadata", False) or metadata)
        self._ui_refresh_flags = flags
        self._ui_refresh_reason = str(reason)
        timer = getattr(self, "_ui_refresh_timer", None)
        if timer is not None:
            timer.start()

    def _flush_ui_refresh(self) -> None:
        """Apply one queued GUI refresh batch."""
        flags = dict(getattr(self, "_ui_refresh_flags", {}) or {})
        if flags.get("table", False) and hasattr(self, "_refresh_table"):
            self._refresh_table()
        if flags.get("metadata", False) and hasattr(self, "_refresh_metadata_dock"):
            try:
                self._refresh_metadata_dock(self.primary_image.id)
            except Exception:
                logger.warning("Failed to refresh metadata dock during queued UI refresh", exc_info=True)
        if flags.get("image", False):
            self._refresh_image()
        if flags.get("status", False) and hasattr(self, "_update_status"):
            self._update_status()
        self._ui_refresh_flags = {
            "image": False,
            "table": False,
            "status": False,
            "metadata": False,
        }
