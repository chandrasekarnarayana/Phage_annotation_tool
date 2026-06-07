"""Derived status builder for the compact status bar and details panel.

This module keeps status derivation separate from widget rendering so the
presenter can stay focused on message priority, timing, and anti-flicker
behavior. The builder reads already-available GUI/session state and assembles
one structured snapshot that feeds both the bottom status bar and the expanded
details panel.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

from phage_annotator.ui_qt.assist_state import AssistState, assist_state_label
from phage_annotator.ui_qt.services.status import StatusModel, StatusText


from phage_annotator.ui_qt.services.status_derived_core import DerivedStatusSnapshot
from phage_annotator.ui_qt.services.status_snapshot import build_status_snapshot
