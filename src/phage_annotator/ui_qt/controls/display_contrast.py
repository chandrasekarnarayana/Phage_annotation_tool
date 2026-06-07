"""Brightness/contrast and display-setting helpers."""

from __future__ import annotations

from typing import Optional

import numpy as np
from matplotlib.backends.qt_compat import QtCore, QtGui

from phage_annotator.ui_qt.services.panel_logging import get_panel_logger


from phage_annotator.ui_qt.controls.display_contrast_controls import DisplayContrastControls
from phage_annotator.ui_qt.controls.display_contrast_sync import DisplayContrastSync


class DisplayContrastMixin(DisplayContrastControls, DisplayContrastSync):
    """Mixin for brightness/contrast and display-setting controls."""

    pass
