"""Navigation commands for keyboard-first workflows.

Commands for jumping to specific frames (T) and Z slices, supporting
keyboard-first navigation with undo/redo support.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Optional

if TYPE_CHECKING:
    from phage_annotator.session.controller import SessionController

from phage_annotator.session.commands import Command, CommandMemento


class JumpToFrameCommand(Command):
    """Command to jump to a specific time frame (T index).
    
    This command supports keyboard-first workflows where users can type
    a frame number to jump to that location directly.
    """
    
    def __init__(
        self,
        controller: "SessionController",
        image_id: int,
        target_t: int,
    ):
        """Initialize jump-to-frame command.
        
        Parameters
        ----------
        controller : SessionController
            Session controller.
        image_id : int
            Image ID (used for grouping).
        target_t : int
            Target T frame index.
        """
        super().__init__(controller, image_id)
        self.target_t = target_t
        self.old_t: Optional[int] = None
    
    def execute(self) -> bool:
        """Execute jump to target frame.
        
        Returns
        -------
        bool
            True if jump was successful, False otherwise.
        """
        # Validate target frame is within bounds
        image = self.controller.session_state.images[self.image_id]
        t_size = image.shape[0] if image.shape else 1
        
        if self.target_t < 0 or self.target_t >= t_size:
            return False
        
        # Store old state
        self.old_t = self.controller.view_state.t
        
        # Create before memento
        self.memento_before = CommandMemento(
            command_type="jump_to_frame",
            image_id=self.image_id,
            data={"old_t": self.old_t},
        )
        
        # Update frame index
        self.controller.set_t(self.target_t)
        
        # Create after memento
        self.memento_after = CommandMemento(
            command_type="jump_to_frame",
            image_id=self.image_id,
            data={"new_t": self.target_t},
        )
        
        return True
    
    def undo(self) -> bool:
        """Undo jump to previous frame."""
        if self.memento_before is None:
            return False
        old_t = self.memento_before.data.get("old_t")
        if old_t is None:
            return False
        self.controller.set_t(int(old_t))
        return True
    
    def redo(self) -> bool:
        """Redo jump to target frame."""
        if self.memento_after is None:
            return False
        
        self.controller.set_t(self.target_t)
        return True

    def emit_change_signals(self) -> None:
        """`set_t` already emits typed view notifications."""
        return None


class JumpToZCommand(Command):
    """Command to jump to a specific Z slice (depth index).
    
    This command supports keyboard-first workflows where users can type
    a Z index to jump to that slice directly.
    """
    
    def __init__(
        self,
        controller: "SessionController",
        image_id: int,
        target_z: int,
    ):
        """Initialize jump-to-z command.
        
        Parameters
        ----------
        controller : SessionController
            Session controller.
        image_id : int
            Image ID (used for grouping).
        target_z : int
            Target Z slice index.
        """
        super().__init__(controller, image_id)
        self.target_z = target_z
        self.old_z: Optional[int] = None
    
    def execute(self) -> bool:
        """Execute jump to target Z slice.
        
        Returns
        -------
        bool
            True if jump was successful, False otherwise.
        """
        # Validate target Z is within bounds
        image = self.controller.session_state.images[self.image_id]
        z_size = image.shape[1] if len(image.shape) > 1 else 1
        
        if self.target_z < 0 or self.target_z >= z_size:
            return False
        
        # Store old state
        self.old_z = self.controller.view_state.z
        
        # Create before memento
        self.memento_before = CommandMemento(
            command_type="jump_to_z",
            image_id=self.image_id,
            data={"old_z": self.old_z},
        )
        
        # Update Z index
        self.controller.set_z(self.target_z)
        
        # Create after memento
        self.memento_after = CommandMemento(
            command_type="jump_to_z",
            image_id=self.image_id,
            data={"new_z": self.target_z},
        )
        
        return True
    
    def undo(self) -> bool:
        """Undo jump to previous Z slice."""
        if self.memento_before is None:
            return False
        old_z = self.memento_before.data.get("old_z")
        if old_z is None:
            return False
        self.controller.set_z(int(old_z))
        return True
    
    def redo(self) -> bool:
        """Redo jump to target Z slice."""
        if self.memento_after is None:
            return False
        
        self.controller.set_z(self.target_z)
        return True

    def emit_change_signals(self) -> None:
        """`set_z` already emits typed view notifications."""
        return None
