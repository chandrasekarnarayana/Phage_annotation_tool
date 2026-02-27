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


class SetROICommand(Command):
    """Command to change ROI (P3.1)."""
    
    def __init__(
        self,
        controller: "SessionController",
        image_id: int,
        new_roi_shape: str,
        new_roi_rect: Tuple[float, float, float, float],
    ):
        super().__init__(controller, image_id)
        self.new_roi_shape = new_roi_shape
        self.new_roi_rect = new_roi_rect
    
    def execute(self) -> bool:
        # Capture current state
        view_state = self.controller.view_state
        self.memento_before = CommandMemento(
            command_type="set_roi",
            image_id=self.image_id,
            data={
                "roi_shape": view_state.roi_shape,
                "roi_rect": view_state.roi_rect,
            },
        )
        
        # Apply new state
        view_state.roi_shape = self.new_roi_shape
        view_state.roi_rect = self.new_roi_rect
        
        # Capture after state
        self.memento_after = CommandMemento(
            command_type="set_roi",
            image_id=self.image_id,
            data={
                "roi_shape": self.new_roi_shape,
                "roi_rect": self.new_roi_rect,
            },
        )
        return True
    
    def undo(self) -> bool:
        if not self.memento_before:
            return False
        view_state = self.controller.view_state
        view_state.roi_shape = self.memento_before.data["roi_shape"]
        view_state.roi_rect = self.memento_before.data["roi_rect"]
        return True
    
    def redo(self) -> bool:
        if not self.memento_after:
            return False
        view_state = self.controller.view_state
        view_state.roi_shape = self.memento_after.data["roi_shape"]
        view_state.roi_rect = self.memento_after.data["roi_rect"]
        return True


class SetCropCommand(Command):
    """Command to change crop region (P3.1)."""
    
    def __init__(
        self,
        controller: "SessionController",
        image_id: int,
        new_crop_rect: Optional[Tuple[float, float, float, float]],
    ):
        super().__init__(controller, image_id)
        self.new_crop_rect = new_crop_rect
    
    def execute(self) -> bool:
        view_state = self.controller.view_state
        self.memento_before = CommandMemento(
            command_type="set_crop",
            image_id=self.image_id,
            data={"crop_rect": view_state.crop_rect},
        )
        
        view_state.crop_rect = self.new_crop_rect
        
        self.memento_after = CommandMemento(
            command_type="set_crop",
            image_id=self.image_id,
            data={"crop_rect": self.new_crop_rect},
        )
        return True
    
    def undo(self) -> bool:
        if not self.memento_before:
            return False
        self.controller.view_state.crop_rect = self.memento_before.data["crop_rect"]
        return True
    
    def redo(self) -> bool:
        if not self.memento_after:
            return False
        self.controller.view_state.crop_rect = self.memento_after.data["crop_rect"]
        return True


class SetDisplayMappingCommand(Command):
    """Command to change display mapping (vmin/vmax/gamma) (P3.1)."""
    
    def __init__(
        self,
        controller: "SessionController",
        image_id: int,
        panel: str,
        new_vmin: float,
        new_vmax: float,
        new_gamma: float,
    ):
        super().__init__(controller, image_id)
        self.panel = panel
        self.new_vmin = new_vmin
        self.new_vmax = new_vmax
        self.new_gamma = new_gamma
    
    def execute(self) -> bool:
        mapping = self.controller.display_mapping.mapping_for(self.image_id, self.panel)
        self.memento_before = CommandMemento(
            command_type="set_display_mapping",
            image_id=self.image_id,
            data={
                "panel": self.panel,
                "vmin": float(mapping.min_val),
                "vmax": float(mapping.max_val),
                "gamma": float(mapping.gamma),
            },
        )
        
        mapping.set_window(self.new_vmin, self.new_vmax)
        mapping.gamma = self.new_gamma
        
        self.memento_after = CommandMemento(
            command_type="set_display_mapping",
            image_id=self.image_id,
            data={
                "panel": self.panel,
                "vmin": self.new_vmin,
                "vmax": self.new_vmax,
                "gamma": self.new_gamma,
            },
        )
        return True
    
    def undo(self) -> bool:
        if not self.memento_before:
            return False
        mapping = self.controller.display_mapping.mapping_for(self.image_id, self.panel)
        mapping.set_window(
            self.memento_before.data["vmin"],
            self.memento_before.data["vmax"],
        )
        mapping.gamma = self.memento_before.data["gamma"]
        return True
    
    def redo(self) -> bool:
        if not self.memento_after:
            return False
        mapping = self.controller.display_mapping.mapping_for(self.image_id, self.panel)
        mapping.set_window(
            self.memento_after.data["vmin"],
            self.memento_after.data["vmax"],
        )
        mapping.gamma = self.memento_after.data["gamma"]
        return True


class SetThresholdCommand(Command):
    """Command to change threshold parameters (P3.1)."""
    
    def __init__(
        self,
        controller: "SessionController",
        image_id: int,
        new_settings: dict,
    ):
        super().__init__(controller, image_id)
        self.new_settings = new_settings
    
    def execute(self) -> bool:
        # Get current threshold settings for this image
        current = self.controller.session_state.threshold_configs_by_image.get(
            self.image_id, {}
        )
        self.memento_before = CommandMemento(
            command_type="set_threshold",
            image_id=self.image_id,
            data={"settings": dict(current)},
        )
        
        # Apply new settings
        self.controller.session_state.threshold_configs_by_image[self.image_id] = (
            dict(self.new_settings)
        )
        
        self.memento_after = CommandMemento(
            command_type="set_threshold",
            image_id=self.image_id,
            data={"settings": dict(self.new_settings)},
        )
        return True
    
    def undo(self) -> bool:
        if not self.memento_before:
            return False
        self.controller.session_state.threshold_configs_by_image[self.image_id] = dict(
            self.memento_before.data["settings"]
        )
        return True
    
    def redo(self) -> bool:
        if not self.memento_after:
            return False
        self.controller.session_state.threshold_configs_by_image[self.image_id] = dict(
            self.memento_after.data["settings"]
        )
        return True


def command_from_dict(data: dict, controller: "SessionController") -> Optional[Command]:
    """Reconstruct a Command object from serialized data (P3.1)."""
    cmd_type = data.get("type")
    image_id = data.get("image_id")
    before = data.get("before")
    after = data.get("after")
    
    if not all([cmd_type, image_id is not None, before, after]):
        return None
    
    # Create appropriate command type
    if cmd_type == "SetROICommand":
        cmd = SetROICommand(
            controller,
            image_id,
            after["data"]["roi_shape"],
            tuple(after["data"]["roi_rect"]),
        )
    elif cmd_type == "SetCropCommand":
        crop = after["data"]["crop_rect"]
        cmd = SetCropCommand(controller, image_id, tuple(crop) if crop else None)
    elif cmd_type == "SetDisplayMappingCommand":
        cmd = SetDisplayMappingCommand(
            controller,
            image_id,
            after["data"]["panel"],
            after["data"]["vmin"],
            after["data"]["vmax"],
            after["data"]["gamma"],
        )
    elif cmd_type == "SetThresholdCommand":
        cmd = SetThresholdCommand(controller, image_id, after["data"]["settings"])
    elif cmd_type == "JumpToFrameCommand":
        from phage_annotator.session.navigation_commands import JumpToFrameCommand

        cmd = JumpToFrameCommand(controller, image_id, int(after["data"]["new_t"]))
    elif cmd_type == "JumpToZCommand":
        from phage_annotator.session.navigation_commands import JumpToZCommand

        cmd = JumpToZCommand(controller, image_id, int(after["data"]["new_z"]))
    elif cmd_type == "DeleteNearestCommand":
        from phage_annotator.session.context_commands import DeleteNearestCommand

        cmd = DeleteNearestCommand(controller, image_id, x=0.0, y=0.0, radius=0.0)
    elif cmd_type == "MarkUncertainCommand":
        from phage_annotator.session.context_commands import MarkUncertainCommand

        uncertain = bool(after["data"].get("is_uncertain", True))
        cmd = MarkUncertainCommand(
            controller,
            image_id,
            x=0.0,
            y=0.0,
            radius=0.0,
            uncertain=uncertain,
        )
    elif cmd_type == "EditNearestMetadataCommand":
        from phage_annotator.session.context_commands import EditNearestMetadataCommand

        cmd = EditNearestMetadataCommand(
            controller,
            image_id,
            x=0.0,
            y=0.0,
            radius=0.0,
            annotation_id=after["data"].get("annotation_id"),
            new_label=after["data"].get("new_label"),
            new_meta=dict(after["data"].get("new_meta", {})),
        )
    elif cmd_type == "SnapToLocalMaxCommand":
        from phage_annotator.session.context_commands import SnapToLocalMaxCommand

        cmd = SnapToLocalMaxCommand(
            controller,
            image_id,
            x=0.0,
            y=0.0,
            radius=0.0,
            search_radius=0.0,
            image_data=None,
        )
    else:
        return None
    
    # Restore mementos
    cmd.memento_before = CommandMemento(**before)
    cmd.memento_after = CommandMemento(**after)
    return cmd


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
        for cmd in self.commands:
            if not cmd.redo():
                success = False
                break
        
        return success
