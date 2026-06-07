"""Annotation import/export, indexing, and merge helpers."""

from __future__ import annotations

import pathlib
from typing import Dict, List, Optional, Tuple

from matplotlib.backends.qt_compat import QtWidgets

from phage_annotator.io.metadata.index import AnnotationIndexEntry, build_index, match
from phage_annotator.io.metadata.annotation import (
    merge_meta,
    parse_csv_header_meta,
    parse_filename_tokens,
    parse_json_meta,
)
from phage_annotator.annotation.core import Keypoint, keypoints_from_csv, keypoints_from_json
from phage_annotator.config import SUPPORTED_SUFFIXES
from phage_annotator.io.readers.annotations import (
    detect_format,
    parse_legacy_csv,
    parse_thunderstorm_csv,
)
from phage_annotator.session.signal_hub import emit_annotations_changed


from phage_annotator.session.annotation_io_methods1 import _SessionAnnotationIOMixinMethods1
from phage_annotator.session.annotation_io_methods2 import _SessionAnnotationIOMixinMethods2

class SessionAnnotationIOMixin(_SessionAnnotationIOMixinMethods1, _SessionAnnotationIOMixinMethods2):
    """Mixin for annotation import/export, indexing, and merge helpers."""

    pass
