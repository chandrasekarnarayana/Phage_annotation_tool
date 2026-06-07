"""Data types for keyboard shortcut definitions and conflict reports."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Callable, Dict, List, Optional, Set, Tuple

try:
    from matplotlib.backends.qt_compat import QtGui, QtCore
except ImportError:
    from PySide6 import QtGui, QtCore


class ShortcutContext(Enum):
    """Context where a shortcut can be active."""
    GLOBAL = "global"           # Always active
    EDITING = "editing"         # When editing annotations
    BROWSING = "browsing"       # When browsing (not editing)
    MODALITY_VIEW = "modality"  # When modality/image is loaded
    TEXT_INPUT = "text_input"   # Never active (text input focus)

@dataclass
class ShortcutDefinition:
    """Definition of a single keyboard shortcut."""

    id: str                          # Unique identifier (e.g., "nav.jump_to_frame")
    category: str                    # Category for organization (e.g., "navigation", "editing")
    description: str                 # Human-readable description
    default_sequence: str            # QKeySequence-compatible string (e.g., "Ctrl+G")
    alternative_sequences: List[str] = field(default_factory=list)  # Alternative shortcuts
    context: ShortcutContext = ShortcutContext.GLOBAL
    enabled: bool = True
    callback: Optional[Callable] = None  # Callable to invoke when shortcut activated

    def __eq__(self, other: object) -> bool:
        """Compare shortcuts by ID."""
        if not isinstance(other, ShortcutDefinition):
            return False
        return self.id == other.id

    def __hash__(self) -> int:
        """Hash by ID."""
        return hash(self.id)

    def all_sequences(self) -> List[str]:
        """Return all key sequences (primary + alternatives)."""
        return [self.default_sequence] + self.alternative_sequences

@dataclass
class ShortcutConflict:
    """Report of a shortcut conflict between two shortcuts."""

    shortcut_a: ShortcutDefinition
    shortcut_b: ShortcutDefinition
    sequence: str  # The conflicting key sequence
    severity: str = "warning"  # "warning" or "error"

    def __str__(self) -> str:
        """Format conflict as human-readable string."""
        return (
            f"Shortcut conflict on '{self.sequence}':\n"
            f"  [{self.shortcut_a.category}] {self.shortcut_a.description} "
            f"(ID: {self.shortcut_a.id})\n"
            f"  [{self.shortcut_b.category}] {self.shortcut_b.description} "
            f"(ID: {self.shortcut_b.id})\n"
            f"Severity: {self.severity}"
        )
