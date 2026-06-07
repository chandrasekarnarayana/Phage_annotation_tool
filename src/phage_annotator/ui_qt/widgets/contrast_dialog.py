"""Brightness and contrast adjustment dialog with histogram preview."""

from __future__ import annotations

from typing import Callable, Optional, Tuple

import numpy as np
from matplotlib.backends.backend_qt5agg import FigureCanvasQTAgg
from matplotlib.backends.qt_compat import QtCore, QtWidgets
from matplotlib.figure import Figure

from phage_annotator.ui_qt.utils.contrast_lut import computeHistogram, autoScaleHistogram


from phage_annotator.ui_qt.widgets.histogram_contrast import HistogramContrastMixin
from phage_annotator.ui_qt.widgets.histogram_contrast_autorange import HistogramContrastAutosetMixin

class ContrastDialog(HistogramContrastMixin, HistogramContrastAutosetMixin, QtWidgets.QDialog):
    """Dialog for interactive brightness/contrast adjustment.

Parameters
----------
parent : QtWidgets.QWidget
    Parent widget.
data : np.ndarray
    2D image data used to compute the histogram.
vmin : float
    Initial minimum value.
vmax : float
    Initial maximum value.
on_apply : Callable[[float, float], None]
    Callback invoked when Apply is pressed."""

    pass
