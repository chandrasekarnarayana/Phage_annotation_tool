"""Services status derived core helpers for the phage annotation tool.

This module was split from a larger implementation to keep responsibilities
small and file sizes manageable.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

from phage_annotator.ui_qt.assist_state import AssistState, assist_state_label
from phage_annotator.ui_qt.services.status import StatusModel, StatusText


@dataclass(slots=True)
class DerivedStatusSnapshot:
    """Structured snapshot shared by compact and detailed status views."""

    model: StatusModel
    dataset_name: str
    frame_txt: str
    current_count: int
    total_count: int
    scope_state: str
    target_state: str
    modality_txt: str
    assist_state: AssistState
    assist_need: int
    freshness: dict[str, Any]
    tool_name: str
    cache_mb: float
    cache_items: int
    action_enabled: dict[str, bool]
    action_disabled_reason: dict[str, str]
