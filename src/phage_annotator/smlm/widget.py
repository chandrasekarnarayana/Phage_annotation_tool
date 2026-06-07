"""Qt widget for ThunderSTORM-style SMLM controls."""

from __future__ import annotations

import csv
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Callable, Iterable, Optional

from matplotlib.backends.qt_compat import QtCore, QtWidgets
from phage_annotator.smlm.backends import discover_bundled_thunderstorm_jar
from phage_annotator.smlm.context_menu import ContextMenuMixin
from phage_annotator.smlm.dock_widget_handlers import DockWidgetHandlersMixin
from phage_annotator.smlm.dock_widget_ui import DockWidgetUiMixin

from phage_annotator.smlm.external_plugins import discover_external_fiji_plugins




from dataclasses import dataclass
from datetime import datetime
from matplotlib.backends.qt_compat import QtCore, QtWidgets
from pathlib import Path
from typing import Callable, Iterable, Optional
import csv

from phage_annotator.smlm.backends import discover_bundled_thunderstorm_jar
from phage_annotator.smlm.external_plugins import discover_external_fiji_plugins


@dataclass
class SmlmUiValues:
    """Snapshot of SMLM parameter values from the UI."""

    sigma_px: float
    fit_radius_px: int
    filter_type: str
    dog_sigma1: float
    dog_sigma2: float
    detection_thr_sigma: float
    max_candidates_per_frame: int
    merge_radius_px: float
    min_photons: float
    max_uncertainty_nm: float
    upsample: int
    render_mode: str
    render_sigma_nm: float
    backend: str
    plugin_id: str
    fiji_executable: str
    fiji_macro_path: str
    plugin_jar_path: str
    thunderstorm_jar_path: str
    fiji_command_template: str
    pyimagej_app_path: str
    reproducibility_mode: bool


class SmlmDockWidget(ContextMenuMixin, DockWidgetHandlersMixin, DockWidgetUiMixin, QtWidgets.QWidget):
    """Parameter panel for the ThunderSTORM-style pipeline."""

    pass
