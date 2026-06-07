"""Annotation suggestion and review action mixins.

Re-exports from semantic sub-modules.
"""
from __future__ import annotations

from phage_annotator.ui_qt.actions.actions_annotation_context2 import ActionsAnnotationContextMixin2
from phage_annotator.ui_qt.actions.actions_suggestion_visibility import ActionsSuggestionVisibilityMixin
from phage_annotator.ui_qt.actions.actions_review_queue import ActionsReviewQueueMixin
from phage_annotator.ui_qt.actions.actions_uncertain_navigation import ActionsUncertainNavigationMixin
from phage_annotator.ui_qt.actions.actions_review_state import ActionsReviewStateMixin


class ActionsMixinAnnotation(
    ActionsAnnotationContextMixin2,
    ActionsSuggestionVisibilityMixin,
    ActionsReviewQueueMixin,
    ActionsUncertainNavigationMixin,
    ActionsReviewStateMixin,
):
    """Combined annotation and suggestion review action mixin."""
    pass
