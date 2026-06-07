"""Method group 2 split from annotation_io.py."""

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


class _SessionAnnotationIOMixinMethods2:
    """Methods split from SessionAnnotationIOMixin."""

    def _dedup_annotations(self, points: List[Keypoint], eps: float = 0.25) -> List[Keypoint]:
        """Document the dedup_annotations flow."""
        seen_ids = set()
        seen_keys = set()
        deduped: List[Keypoint] = []
        for kp in points:
            if kp.annotation_id:
                if kp.annotation_id in seen_ids:
                    continue
                seen_ids.add(kp.annotation_id)
            else:
                key = (
                    int(round(kp.x / eps)),
                    int(round(kp.y / eps)),
                    int(kp.t),
                    int(kp.z),
                    kp.label,
                    kp.meta.get("import_file", ""),
                )
                if key in seen_keys:
                    continue
                seen_keys.add(key)
            deduped.append(kp)
        return deduped

    def load_indexed_annotations(self, image_id: int, pixel_size_nm: Optional[float]) -> List[Keypoint]:
        """Parse annotation files from the index for a single image."""
        entries = self.annotation_entries_for_image(image_id)
        if not entries:
            return []
        paths = [entry.path for entry in entries]
        points, imports = self._parse_annotations_from_paths(
            paths,
            image_id=image_id,
            pixel_size_nm=pixel_size_nm,
            force_image_id=image_id,
        )
        self._record_annotation_imports(imports)
        return points

    def replace_annotations(self, image_id: int, points: List[Keypoint]) -> None:
        """Replace annotations for an image with a deduplicated list."""
        self.session_state.annotations[image_id] = self._dedup_annotations(points)
        self.mark_annotations_loaded(image_id)

    def merge_annotations(self, image_id: int, points: List[Keypoint]) -> None:
        """Merge annotations for an image with deduplication."""
        self._merge_annotations(image_id, points)
        self.mark_annotations_loaded(image_id)

    def clear_annotations(self, image_id: int) -> None:
        """Remove all annotations for an image."""
        self.session_state.annotations[image_id] = []
