"""Method group 2 split from learning_model_core.py."""

from __future__ import annotations

import pickle
from dataclasses import dataclass, field
from pathlib import Path
from typing import List, Literal, Optional

import numpy as np

from phage_annotator.core.annotation import PointSuggestion
from phage_annotator.analysis.training_data import TrainingExample


@dataclass

class _InteractiveLearningModelMethods2:
    """Methods split from InteractiveLearningModel."""

    @classmethod
    def load(cls, path: str | Path) -> "InteractiveLearningModel":
        """Load model from disk."""
        with open(path, "rb") as f:
            state = pickle.load(f)

        model = cls(
            model_type=state["model_type"],
            update_frequency=state.get("update_frequency", 10),
            min_examples_to_train=state.get("min_examples_to_train", 20),
            confidence_threshold=state.get("confidence_threshold", 0.5),
        )

        model.classifier = state["classifier"]
        model.feature_names = state["feature_names"]
        model.training_examples = state["training_examples"]
        model.is_trained = state["is_trained"]
        model.model_version = state["model_version"]
        model.n_accepted = state.get("n_accepted", 0)
        model.n_rejected = state.get("n_rejected", 0)
        model.last_accuracy = state.get("last_accuracy", 0.0)

        return model

    def get_statistics(self) -> dict:
        """Get model statistics."""
        return {
            "is_trained": self.is_trained,
            "model_version": self.model_version,
            "n_training_examples": len(self.training_examples),
            "n_accepted": self.n_accepted,
            "n_rejected": self.n_rejected,
            "last_accuracy": self.last_accuracy,
            "feature_count": len(self.feature_names),
        }

    def get_feature_importance(self) -> dict[str, float]:
        """Get feature importance from trained model."""
        if not self.is_trained or not hasattr(self.classifier, "feature_importances_"):
            return {}

        importances = self.classifier.feature_importances_
        return dict(zip(self.feature_names, importances))

    def reset(self) -> None:
        """Reset the model to untrained state (keeps configuration)."""
        self._initialize_classifier()
        self.training_examples.clear()
        self.is_trained = False
        self.model_version = 0
        self.n_accepted = 0
        self.n_rejected = 0
        self.last_accuracy = 0.0
