"""Project/session snapshot bridge and load/apply helpers."""

from __future__ import annotations

import pathlib
from typing import Dict, List

from matplotlib.backends.qt_compat import QtWidgets

from phage_annotator.annotation.core import PointSuggestion, keypoints_from_json
from phage_annotator.config.density import DensityConfig
from phage_annotator.core.workspace_snapshot import apply_workspace_snapshot_to_controller
from phage_annotator.data.display_mapping import mapping_from_dict
from phage_annotator.roi.manager import roi_from_dict
from phage_annotator.session.signal_hub import emit_annotations_changed, emit_state_changed


from phage_annotator.session.project_bridge_methods1 import _SessionProjectBridgeMixinMethods1
from phage_annotator.session.project_bridge_methods2 import _SessionProjectBridgeMixinMethods2

class SessionProjectBridgeMixin(_SessionProjectBridgeMixinMethods1, _SessionProjectBridgeMixinMethods2):
    """Mixin for loading project payloads into controller/session state."""

    pass
