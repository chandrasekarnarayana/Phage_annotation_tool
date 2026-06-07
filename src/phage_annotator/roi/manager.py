"""ROI manager data model and JSON I/O with atomic, schema-versioned persistence."""

from __future__ import annotations

import json
import logging
import shutil
import tempfile
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, Iterable, List, Optional, Tuple

logger = logging.getLogger(__name__)


from phage_annotator.roi.manager_core import Roi
from phage_annotator.roi.manager_core import RoiManager
from phage_annotator.roi.roi_serialization import roi_to_dict, roi_from_dict, save_rois_json, load_rois_json
