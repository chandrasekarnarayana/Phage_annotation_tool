"""Method group 2 split from events_wiring.py."""

from __future__ import annotations

import logging

from matplotlib.backends.qt_compat import QtCore, QtGui, QtWidgets

from phage_annotator.ui_qt.assist_state import assist_state_label
from phage_annotator.ui_qt.actions.keyboard_events import KeyboardEventsMixin

logger = logging.getLogger(__name__)

class _EventsWiringMixinMethods2:
    """Methods split from EventsWiringMixin."""

    def _bind_controller_signals(self) -> None:
        """Bind immediate Qt controller signals used for GUI synchronization."""
        self.controller.annotations_changed.connect(
            lambda: (
                self._request_ui_refresh("controller-annotations", table=True, image=True, status=True),
                QtCore.QTimer.singleShot(0, self._refresh_assist_warmup_panel),
            )
        )
        self.controller.view_changed.connect(self._on_controller_view_changed)
        self.controller.state_changed.connect(
            lambda: (
                self._schedule_lazy_panel_sync("controller-state"),
                self._request_ui_refresh("controller-state", image=False, table=False, status=True, metadata=True),
            )
        )
        self.controller.display_changed.connect(
            lambda: (
                self._schedule_lazy_panel_sync("controller-display"),
                self._request_ui_refresh("controller-display", image=True, status=True),
            )
        )

    def _bind_application_events(self) -> None:
        """Subscribe to application-level events from the event bus.
        
        This integrates GUI with the event service, allowing components
        to react to state changes without direct coupling.
        """
        try:
            from phage_annotator.framework import get_event_service
            from phage_annotator.framework.events import (
                AnnotationChangedEvent,
                ViewStateChangedEvent,
                CacheInvalidationEvent,
            )
            
            event_service = get_event_service()
            
            subscriptions = (
                (AnnotationChangedEvent, self._on_annotations_changed_event),
                (ViewStateChangedEvent, self._on_view_state_changed_event),
                (CacheInvalidationEvent, self._on_cache_invalidation_event),
            )
            for event_type, handler in subscriptions:
                event_service.subscribe(event_type, handler)
        except (ImportError, AttributeError, RuntimeError):
            # Event service not available or not initialized; continue gracefully
            pass

    def _bind_axis_callbacks(self) -> None:
        """Bind zoom callbacks for current axes to keep zoom synced."""
        axes = []
        if getattr(self, "renderer", None) is not None:
            axes = [ax for ax in self.renderer.axes.values() if ax is not None]
        for ax in axes:
            ax.callbacks.connect("xlim_changed", self._on_limits_changed)
            ax.callbacks.connect("ylim_changed", self._on_limits_changed)
