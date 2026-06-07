"""Split definitions from test_multimodality_workflows.py."""

from __future__ import annotations

import json
import tempfile
from pathlib import Path

from phage_annotator.annotation.core import Keypoint
from phage_annotator.data.display_mapping import DisplayMapping
from phage_annotator.session.modality import ModalityManager


def _make_keypoint(
    *,
    x: float,
    y: float,
    modality_idx: int | None,
    image_id: int = 0,
    image_name: str = "img.tif",
    t: int = 0,
    z: int = 0,
    label: str = "test",
) -> Keypoint:
    """Create a test keypoint using the current core annotation schema."""
    return Keypoint(
        image_id=image_id,
        image_name=image_name,
        t=t,
        z=z,
        y=y,
        x=x,
        label=label,
        modality_idx=modality_idx,
    )

def _visible_annotations(annotations: list[Keypoint], active_modality_idx: int) -> list[Keypoint]:
    """Return annotations visible for a given active modality."""
    return [
        ann
        for ann in annotations
        if ann.modality_idx is None or ann.modality_idx == active_modality_idx
    ]
