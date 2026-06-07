"""Lightweight proposal ranking and calibration for assisted annotation.

Definitions are split into sibling modules to keep this compatibility surface small.
"""

from phage_annotator.analysis.suggestion_ranker_split1 import _sigmoid, calibration_bins, expected_calibration_error, feature_vector_from_suggestion
from phage_annotator.analysis.suggestion_ranker_split2 import LightweightSuggestionRanker, dataset_metrics_from_suggestions
