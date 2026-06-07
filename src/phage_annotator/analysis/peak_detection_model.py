"""Final LocalPeakSuggestionModel: spatial filtering, NMS, and public predict API.

Assembles feature extraction and candidate collection mixins into the full model.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import List

import numpy as np

from phage_annotator.core.annotation import PointSuggestion
from phage_annotator.analysis.peak_candidate_collection import LocalPeakCandidateCollector



from phage_annotator.analysis.peak_detection_model_methods1 import _LocalPeakSuggestionModelMethods1
from phage_annotator.analysis.peak_detection_model_methods2 import _LocalPeakSuggestionModelMethods2

class LocalPeakSuggestionModel(_LocalPeakSuggestionModelMethods1, _LocalPeakSuggestionModelMethods2, LocalPeakCandidateCollector):
    """Fast baseline model using local maxima as candidate points.

This is the first-level assist for coarse detection. Features extracted here
can be used by downstream ML models (e.g., LightGBM) for fine-tuning."""

    pass
