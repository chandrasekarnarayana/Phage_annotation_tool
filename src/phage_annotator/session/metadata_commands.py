"""Commands for annotation metadata updates (undoable).

Metadata mutations are command-based to support undo/redo and maintain
consistency with the session's command stack.

Definitions are split into sibling modules to keep this compatibility surface small.
"""

from phage_annotator.session.metadata_commands_split1 import _emit_metadata_changed, UpdateMetadataCommand, BulkUpdateMetadataCommand
from phage_annotator.session.metadata_commands_split2 import UpdateLabelCommand
