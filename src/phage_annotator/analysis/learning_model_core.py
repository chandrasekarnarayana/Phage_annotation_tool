"""Core InteractiveLearningModel class: Weka-inspired interactive learning for keypoint detection.

Workflow:
1. Initial predictions using rule-based scoring (25 features)
2. User reviews and labels examples (accept/reject)
3. Model trains incrementally every N examples
4. Predictions update in real-time
5. Model persists for future sessions

Features:
- Incremental learning (updates without full retraining)
- Active learning (suggests uncertain examples)
- Model persistence (save/load per experiment)
- Confidence scores (prediction probabilities)
"""

from __future__ import annotations

import pickle
from dataclasses import dataclass, field
from pathlib import Path
from typing import List, Literal, Optional

import numpy as np

from phage_annotator.core.annotation import PointSuggestion
from phage_annotator.analysis.training_data import TrainingExample



from phage_annotator.analysis.learning_model_core_methods1 import _InteractiveLearningModelMethods1
from phage_annotator.analysis.learning_model_core_methods2 import _InteractiveLearningModelMethods2

class InteractiveLearningModel(_InteractiveLearningModelMethods1, _InteractiveLearningModelMethods2):
    """Weka-inspired interactive learning for keypoint detection."""

    # Configuration
    model_type: Literal["random_forest", "gradient_boosting"] = "random_forest"
    update_frequency: int = 10  # Retrain every N examples
    min_examples_to_train: int = 10  # Minimum examples before first training
    confidence_threshold: float = 0.5  # Threshold for binary prediction
    # Model state
    classifier: Optional[object] = None  # sklearn classifier
    feature_names: List[str] = field(default_factory=list)
    training_examples: List[TrainingExample] = field(default_factory=list)
    is_trained: bool = False
    model_version: int = 0
    # Statistics
    n_accepted: int = 0
    n_rejected: int = 0
    last_accuracy: float = 0.0
