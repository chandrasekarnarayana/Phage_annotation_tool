"""QC workflow actions."""

from __future__ import annotations

import pathlib
import time
from typing import Optional

from matplotlib.backends.qt_compat import QtCore, QtWidgets

from phage_annotator.ui_qt.services.panel_logging import get_panel_logger

DISABLE_QC = True


from phage_annotator.ui_qt.actions.qc_actions_methods1 import _QCActionsMixinMethods1
from phage_annotator.ui_qt.actions.qc_actions_methods2 import _QCActionsMixinMethods2

class QCActionsMixin(_QCActionsMixinMethods1, _QCActionsMixinMethods2):
    """Quality-control issue validation, navigation, and export actions."""

    pass
