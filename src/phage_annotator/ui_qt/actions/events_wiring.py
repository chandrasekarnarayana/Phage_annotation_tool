"""Event wiring and interaction handlers."""

from __future__ import annotations

import logging

from matplotlib.backends.qt_compat import QtCore, QtGui, QtWidgets

from phage_annotator.ui_qt.assist_state import assist_state_label
from phage_annotator.ui_qt.actions.keyboard_events import KeyboardEventsMixin

logger = logging.getLogger(__name__)

from phage_annotator.ui_qt.actions.events_wiring_methods1 import _EventsWiringMixinMethods1
from phage_annotator.ui_qt.actions.events_wiring_methods2 import _EventsWiringMixinMethods2

class EventsWiringMixin(_EventsWiringMixinMethods1, _EventsWiringMixinMethods2):
    """Signal and event binding setup."""

    pass
