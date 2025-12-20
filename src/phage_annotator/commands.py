"""Command pattern for undo/redo of view state operations (P3.1).

This module extends the existing annotation undo/redo system to support
view state operations like ROI changes, crop operations, display mapping
adjustments, and threshold parameter changes.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import asdict, dataclass, field
from typing import TYPE_CHECKING, Any, Optional, Tuple

if TYPE_CHECKING:
    from phage_annotator.session_controller import SessionController


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
    else:
        return None
    
    # Restore mementos
    cmd.memento_before = CommandMemento(**before)
    cmd.memento_after = CommandMemento(**after)
    return cmd
