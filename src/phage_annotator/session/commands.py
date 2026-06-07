"""Command framework for undo/redo operations.

Re-exports command classes from semantic sub-modules.
"""
from __future__ import annotations

from phage_annotator.session.commands_base import CommandMemento, Command
from phage_annotator.session.commands_display import (
    SetDisplayMappingCommand,
    SetThresholdCommand,
    TransactionCommand,
)
from phage_annotator.session.commands_roi import SetROICommand, SetCropCommand, SetCropFromRoiCommand

def command_from_dict(data: dict, controller: object) -> Command | None:
    """Reconstruct a command object from serialized memento data."""
    cmd_type = data.get("type")
    image_id = data.get("image_id")
    before = data.get("before")
    after = data.get("after")
    if not all([cmd_type, image_id is not None, before, after]):
        return None
    if cmd_type == "SetROICommand":
        cmd = SetROICommand(controller, image_id, after["data"]["roi_shape"], tuple(after["data"]["roi_rect"]))
    elif cmd_type == "SetCropCommand":
        crop = after["data"]["crop_rect"]
        cmd = SetCropCommand(controller, image_id, tuple(crop) if crop else None)
    elif cmd_type == "SetCropFromRoiCommand":
        cmd = SetCropFromRoiCommand(controller, image_id)
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
        cmd = DeleteNearestCommand(controller, image_id, 0.0, 0.0)
    elif cmd_type == "MarkUncertainCommand":
        from phage_annotator.session.context_commands import MarkUncertainCommand
        is_uncertain = bool(after["data"].get("is_uncertain", True))
        cmd = MarkUncertainCommand(controller, image_id, 0.0, 0.0, uncertain=is_uncertain)
    elif cmd_type == "SnapToLocalMaxCommand":
        from phage_annotator.session.context_commands import SnapToLocalMaxCommand
        cmd = SnapToLocalMaxCommand(controller, image_id, 0.0, 0.0)
    elif cmd_type == "EditNearestMetadataCommand":
        from phage_annotator.session.context_commands import EditNearestMetadataCommand
        cmd = EditNearestMetadataCommand(
            controller,
            image_id,
            0.0,
            0.0,
            0.0,
            annotation_id=after["data"].get("annotation_id"),
            new_label=after["data"].get("new_label"),
            new_meta=after["data"].get("new_meta", {}),
        )
    elif cmd_type == "AcceptSuggestionCommand":
        from phage_annotator.session.suggestion_commands import AcceptSuggestionCommand
        sid = before["data"].get("suggestion", {}).get("suggestion_id", "")
        cmd = AcceptSuggestionCommand(controller, image_id, sid)
    elif cmd_type == "RejectSuggestionCommand":
        from phage_annotator.session.suggestion_commands import RejectSuggestionCommand
        sid = before["data"].get("suggestion", {}).get("suggestion_id", "")
        cmd = RejectSuggestionCommand(controller, image_id, sid)
    elif cmd_type == "ClearSuggestionsCommand":
        from phage_annotator.session.suggestion_commands import ClearSuggestionsCommand
        cmd = ClearSuggestionsCommand(controller, image_id)
    else:
        return None
    cmd.memento_before = CommandMemento(**before)
    cmd.memento_after = CommandMemento(**after)
    return cmd

__all__ = [
    "CommandMemento", "Command",
    "SetDisplayMappingCommand", "SetThresholdCommand", "TransactionCommand",
    "SetROICommand", "SetCropCommand", "SetCropFromRoiCommand",
    "command_from_dict",
]
