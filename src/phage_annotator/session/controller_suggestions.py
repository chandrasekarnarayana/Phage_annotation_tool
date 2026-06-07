"""Suggestion workflow controller - aggregator."""
from __future__ import annotations

from phage_annotator.session.suggestion_spatial import SuggestionSpatialMixin
from phage_annotator.session.suggestion_rescore import SuggestionRescoreMixin
from phage_annotator.session.suggestion_pipeline import SuggestionPipelineMixin
from phage_annotator.session.suggestion_generation import SuggestionGenerationMixin
from phage_annotator.session.suggestion_operations import SuggestionOperationsMixin
from phage_annotator.session.suggestion_training import SuggestionTrainingMixin


class SessionControllerSuggestionsMixin(
    SuggestionSpatialMixin,
    SuggestionRescoreMixin,
    SuggestionPipelineMixin,
    SuggestionGenerationMixin,
    SuggestionOperationsMixin,
    SuggestionTrainingMixin,
):
    """Aggregated mixin for the suggestion workflow controller."""
    pass
