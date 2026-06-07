"""Undo/redo command framework for view state changes.

This module extends the existing annotation undo/redo system to support
view state operations like ROI changes, crop operations, display mapping
adjustments, and threshold parameter changes.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import asdict, dataclass, field
from typing import TYPE_CHECKING, Any, Optional, Tuple

if TYPE_CHECKING:
    from phage_annotator.session.controller import SessionController

from phage_annotator.session.signal_hub import (
    annotation_notification_batch,
    emit_display_changed,
    emit_roi_changed,
    emit_state_changed,
    emit_view_changed,
)


@dataclass



class CommandMemento:
    """Snapshot of state for a command (P3.1).
    
    Used to store the before/after state for undo/redo operations.
    """
    command_type: str
    image_id: int
    data: dict = field(default_factory=dict)



class Command(ABC):
    """Abstract base class for undoable commands (P3.1)."""
    
    def __init__(self, controller: "SessionController", image_id: int):
        """Document the init flow."""
        self.controller = controller
        self.image_id = image_id
        self.memento_before: Optional[CommandMemento] = None
        self.memento_after: Optional[CommandMemento] = None
    
    @abstractmethod
    def execute(self) -> bool:
        """Execute the command and store state for undo."""
        pass
    
    @abstractmethod
    def undo(self) -> bool:
        """Undo the command using stored state."""
        pass
    
    @abstractmethod
    def redo(self) -> bool:
        """Redo the command using stored state."""
        pass
    
    def to_dict(self) -> dict:
        """Serialize command for stack storage."""
        return {
            "type": self.__class__.__name__,
            "image_id": self.image_id,
            "before": asdict(self.memento_before) if self.memento_before else None,
            "after": asdict(self.memento_after) if self.memento_after else None,
        }

    def emit_change_signals(self) -> None:
        """Publish command effects after execute/undo/redo.

        Commands that already emit typed notifications during their own mutation
        methods should override this as a no-op to avoid duplicate emissions.
        """
        emit_state_changed(self.controller)
