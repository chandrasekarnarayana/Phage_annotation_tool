"""Training example dataclass and related data structures for interactive learning."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass
class TrainingExample:
    """Single training example with features and label."""

    suggestion_id: str
    features: dict[str, float]
    label: int  # 1 = accepted, 0 = rejected
    image_name: str
    t: int
    z: int
