"""Assist generation and batch suggestion workflow helpers."""

from __future__ import annotations

import os
import time
from typing import List, Optional

from matplotlib.backends.qt_compat import QtCore, QtWidgets

from phage_annotator.core.annotation import PointSuggestion
from phage_annotator.session.suggestion_commands import (
    AcceptSuggestionCommand,
    AcceptSuggestionsBatchCommand,
    ClearSuggestionsCommand,
    RejectSuggestionCommand,
)
from phage_annotator.ui_qt.services.panel_logging import get_panel_logger


from phage_annotator.ui_qt.actions.suggestion_generation import _set_generation_progress, suggest_points_current_slice, suggest_points_current_image
from phage_annotator.ui_qt.actions.suggestion_generation import preview_batch_accept_dialog, accept_visible_suggestions, accept_high_confidence_suggestions, reject_visible_suggestions
from phage_annotator.ui_qt.actions.suggestion_generation import accept_suggestions_in_roi, clear_suggestions_current_image
