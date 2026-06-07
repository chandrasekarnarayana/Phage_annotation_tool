"""Event wiring and interaction handlers - aggregator."""
from __future__ import annotations

from phage_annotator.ui_qt.actions.keyboard_events import KeyboardEventsMixin
from phage_annotator.ui_qt.actions.events_wiring import EventsWiringMixin
from phage_annotator.ui_qt.actions.events_interaction import EventsInteractionMixin


class EventsMixin(KeyboardEventsMixin, EventsWiringMixin, EventsInteractionMixin):
    """Aggregated mixin for Qt/matplotlib event handlers and interaction state."""
    pass
