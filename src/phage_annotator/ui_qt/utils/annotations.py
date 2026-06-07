"""Annotation interaction helpers."""

from __future__ import annotations

from typing import Optional, Tuple

import numpy as np
from matplotlib.backends.qt_compat import QtCore, QtWidgets

from phage_annotator.tools.router import Tool
from phage_annotator.ui_qt.services.panel_logging import get_panel_logger


from phage_annotator.ui_qt.utils.annotations_methods1 import _AnnotationsMixinMethods1
from phage_annotator.ui_qt.utils.annotations_methods2 import _AnnotationsMixinMethods2

class AnnotationsMixin(_AnnotationsMixinMethods1, _AnnotationsMixinMethods2):
    """Mixin for annotation add/remove and profile line edits."""

    pass
