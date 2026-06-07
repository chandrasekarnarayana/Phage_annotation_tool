"""Actions for analysis workflows.

Re-exports action mixin classes from semantic sub-modules.
"""
from __future__ import annotations

from phage_annotator.ui_qt.actions.actions_suggestion_pipeline import ActionsSuggestionPipelineMixin
from phage_annotator.ui_qt.actions.actions_predictions import ActionsPredictionsMixin
from phage_annotator.ui_qt.actions.actions_learning import ActionsLearningMixin
from phage_annotator.ui_qt.actions.actions_analysis_dialogs import ActionsAnalysisDialogsMixin


class ActionsMixinAnalysis(
    ActionsSuggestionPipelineMixin,
    ActionsPredictionsMixin,
    ActionsLearningMixin,
    ActionsAnalysisDialogsMixin,
):
    """Mixin for analysis and suggestion workflow actions."""
    pass
