"""Centralized action mixin for the main GUI window.

Aggregates all action groups from semantic sub-modules.
"""
from __future__ import annotations

from phage_annotator.ui_qt.actions.assist_context import AssistContextMixin
from phage_annotator.ui_qt.actions.assist_strategy import AssistStrategyMixin
from phage_annotator.ui_qt.actions.standard_workspace import WorkspaceActionsMixin
from phage_annotator.ui_qt.actions.navigation_actions import NavigationActionsMixin
from phage_annotator.ui_qt.actions.export_actions import ExportActionsMixin
from phage_annotator.ui_qt.actions.dock_actions import DockActionsMixin
from phage_annotator.ui_qt.actions.qc_actions import QCActionsMixin
from phage_annotator.ui_qt.actions.actions_file import ActionsMixinFile
from phage_annotator.ui_qt.actions.actions_file_open import ActionsFileOpenMixin
from phage_annotator.ui_qt.actions.actions_display import ActionsMixinDisplay
from phage_annotator.ui_qt.actions.actions_modality_layers import ActionsModalityLayersMixin
from phage_annotator.ui_qt.actions.actions_annotation import ActionsMixinAnnotation
from phage_annotator.ui_qt.actions.actions_annotation_context import ActionsAnnotationContextMixin
from phage_annotator.ui_qt.actions.actions_annotation_review import ActionsAnnotationReviewMixin
from phage_annotator.ui_qt.actions.actions_assist_config import ActionsAssistConfigMixin
from phage_annotator.ui_qt.actions.actions_review import ActionsReviewMixin
from phage_annotator.ui_qt.actions.actions_suggestion_ops import ActionsSuggestionOpsMixin
from phage_annotator.ui_qt.actions.actions_uncertain_nav import ActionsUncertainNavMixin
from phage_annotator.ui_qt.actions.actions_model_ops import ActionsModelOpsMixin
from phage_annotator.ui_qt.actions.actions_gating import ActionsGatingMixin
from phage_annotator.ui_qt.actions.actions_bulk_accept import ActionsBulkAcceptMixin
from phage_annotator.ui_qt.actions.actions_panels import ActionsPanelsMixin
from phage_annotator.ui_qt.actions.actions_analysis import ActionsMixinAnalysis
from phage_annotator.session.suggestion_commands import (
    AcceptSuggestionCommand,
    ClearSuggestionsCommand,
    RejectSuggestionCommand,
)


class ActionsMixin(
    AssistContextMixin,
    AssistStrategyMixin,
    WorkspaceActionsMixin,
    NavigationActionsMixin,
    ExportActionsMixin,
    DockActionsMixin,
    QCActionsMixin,
    ActionsMixinFile,
    ActionsFileOpenMixin,
    ActionsMixinDisplay,
    ActionsModalityLayersMixin,
    ActionsMixinAnnotation,
    ActionsAnnotationContextMixin,
    ActionsAnnotationReviewMixin,
    ActionsAssistConfigMixin,
    ActionsReviewMixin,
    ActionsSuggestionOpsMixin,
    ActionsUncertainNavMixin,
    ActionsModelOpsMixin,
    ActionsGatingMixin,
    ActionsBulkAcceptMixin,
    ActionsPanelsMixin,
    ActionsMixinAnalysis,
):
    """Complete action mixin combining all action groups."""
    pass
