"""Suggestion pipeline action mixins.

Re-exports from semantic sub-modules.
"""
from __future__ import annotations

from phage_annotator.ui_qt.actions.actions_pipeline_merge import ActionsPipelineMergeMixin
from phage_annotator.ui_qt.actions.actions_pipeline_batch import ActionsPipelineBatchMixin


class ActionsSuggestionPipelineMixin(ActionsPipelineMergeMixin, ActionsPipelineBatchMixin):
    """Combined suggestion pipeline action mixin."""
    pass
