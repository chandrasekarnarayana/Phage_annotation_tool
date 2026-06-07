"""Split definitions from commands_display.py."""

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
from phage_annotator.session.commands_base import Command, CommandMemento


class TransactionCommand(Command):
    """Command that groups multiple sub-commands as a single transaction.
    
    This enables atomic operations where multiple individual commands are
    treated as a single undo/redo item. Useful for batch operations like
    bulk metadata updates or multi-step context actions.
    """
    
    def __init__(
        self,
        controller: "SessionController",
        image_id: int,
        transaction_name: str,
    ):
        """Initialize transaction command.
        
        Parameters
        ----------
        controller : SessionController
            Session controller.
        image_id : int
            Image ID (used for grouping).
        transaction_name : str
            Human-readable name for the transaction (e.g., "Bulk Update Metadata").
        """
        super().__init__(controller, image_id)
        self.transaction_name = transaction_name
        self.commands: list[Command] = []
        self._executed = False
    
    def add_command(self, cmd: Command) -> None:
        """Add a sub-command to the transaction.
        
        Parameters
        ----------
        cmd : Command
            Command to add. Should not have been executed yet.
        """
        if self._executed:
            raise RuntimeError("Cannot add commands to transaction after execution")
        self.commands.append(cmd)
    
    def execute(self) -> bool:
        """Execute all sub-commands in order.
        
        If any sub-command fails, previously executed commands are NOT
        rolled back. This follows the memento pattern where each command
        stores its own before/after state.
        
        Returns
        -------
        bool
            True if all commands executed successfully, False if any failed.
        """
        if self._executed:
            return False
        
        # Capture pre-transaction state
        mementos_before = []
        for cmd in self.commands:
            mementos_before.append(cmd.memento_before)
        
        # Execute each command
        success = True
        with annotation_notification_batch(self.controller):
            for cmd in self.commands:
                if not cmd.execute():
                    success = False
                    break
        
        # If any failed, capture state and return False
        # (Caller should decide whether to rollback)
        if not success:
            return False
        
        # Create transaction-level mementos
        self.memento_before = CommandMemento(
            command_type="transaction",
            image_id=self.image_id,
            data={
                "name": self.transaction_name,
                "num_commands": len(self.commands),
                "command_mementos": [m.data if m else {} for m in mementos_before],
            },
        )
        
        mementos_after = []
        for cmd in self.commands:
            mementos_after.append(cmd.memento_after)
        
        self.memento_after = CommandMemento(
            command_type="transaction",
            image_id=self.image_id,
            data={
                "name": self.transaction_name,
                "num_commands": len(self.commands),
                "command_mementos": [m.data if m else {} for m in mementos_after],
            },
        )
        
        self._executed = True
        return True
    
    def undo(self) -> bool:
        """Undo all sub-commands in reverse order.
        
        Returns
        -------
        bool
            True if all undo operations succeeded, False otherwise.
        """
        if not self._executed:
            return False
        
        # Undo in reverse order
        success = True
        with annotation_notification_batch(self.controller):
            for cmd in reversed(self.commands):
                if not cmd.undo():
                    success = False
                    break
        
        return success
    
    def redo(self) -> bool:
        """Redo all sub-commands in order.
        
        Returns
        -------
        bool
            True if all redo operations succeeded, False otherwise.
        """
        if not self._executed:
            return False
        
        # Redo in order
        success = True
        with annotation_notification_batch(self.controller):
            for cmd in self.commands:
                if not cmd.redo():
                    success = False
                    break

        return success

    def emit_change_signals(self) -> None:
        """Sub-commands already emit their own notifications."""
        return None
