"""Undo/redo command framework for view state changes.

This module extends the existing annotation undo/redo system to support
view state operations like ROI changes, crop operations, display mapping
adjustments, and threshold parameter changes.

Definitions are split into sibling modules to keep this compatibility surface small.
"""

from phage_annotator.session.commands_display_split1 import SetDisplayMappingCommand, SetThresholdCommand
from phage_annotator.session.commands_display_split2 import TransactionCommand
