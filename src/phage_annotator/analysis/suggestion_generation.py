"""Extracted method group 1 for InteractiveLearningModel."""

from __future__ import annotations

import pickle
from dataclasses import dataclass, field
from pathlib import Path
from typing import List, Literal, Optional

import numpy as np

from phage_annotator.core.annotation import PointSuggestion
from phage_annotator.analysis.training_data import TrainingExample



@dataclass


class SuggestionGenerationMixin:
    """Method group 1 extracted from InteractiveLearningModel."""

    def __post_init__(self):
        """Initialize the classifier."""
        self._initialize_classifier()
    def _initialize_classifier(self) -> None:
        """Create the sklearn classifier."""
        if self.model_type == "random_forest":
            try:
                from sklearn.ensemble import RandomForestClassifier
                self.classifier = RandomForestClassifier(
                    n_estimators=50,
                    max_depth=10,
                    min_samples_split=5,
                    min_samples_leaf=2,
                    random_state=42,
                    n_jobs=-1,  # Parallel execution
                )
            except ImportError:
                raise ImportError("scikit-learn required for interactive learning. Install with: pip install scikit-learn")
        
        elif self.model_type == "gradient_boosting":
            try:
                from sklearn.ensemble import GradientBoostingClassifier
                self.classifier = GradientBoostingClassifier(
                    n_estimators=50,
                    max_depth=5,
                    learning_rate=0.1,
                    subsample=0.8,
                    random_state=42,
                )
            except ImportError:
                raise ImportError("scikit-learn required. Install with: pip install scikit-learn")
    def add_example(self, suggestion: PointSuggestion, accepted: bool) -> bool:
        """Add a training example from user feedback.
        
        Args:
            suggestion: The point suggestion with features
            accepted: Whether user accepted (True) or rejected (False)
        
        Returns:
            True if model was retrained, False otherwise
        """
        example = TrainingExample(
            suggestion_id=suggestion.suggestion_id,
            features=suggestion.score_components.copy(),
            label=1 if accepted else 0,
            image_name=suggestion.image_name,
            t=suggestion.t,
            z=suggestion.z,
        )
        
        self.training_examples.append(example)
        
        if accepted:
            self.n_accepted += 1
        else:
            self.n_rejected += 1
        
        # Update feature names from first example
        if not self.feature_names:
            self.feature_names = sorted(example.features.keys())
        
        # Check if we should retrain
        should_retrain = (
            len(self.training_examples) >= self.min_examples_to_train and
            len(self.training_examples) % self.update_frequency == 0
        )
        
        if should_retrain:
            self.train()
            return True
        
        return False
    def train(self) -> None:
        """Train the model on collected examples."""
        if len(self.training_examples) < self.min_examples_to_train:
            return
        
        # Check class balance
        n_positive = sum(1 for ex in self.training_examples if ex.label == 1)
        n_negative = len(self.training_examples) - n_positive
        
        if n_positive == 0 or n_negative == 0:
            # Need both positive and negative examples
            return
        
        # Extract features and labels
        X = self._extract_feature_matrix(self.training_examples)
        y = np.array([ex.label for ex in self.training_examples])
        
        # Train the classifier
        self.classifier.fit(X, y)
        self.is_trained = True
        self.model_version += 1
        
        # Estimate accuracy (simple in-sample for now)
        y_pred = self.classifier.predict(X)
        self.last_accuracy = float(np.mean(y_pred == y))
    def predict(self, suggestions: List[PointSuggestion]) -> List[dict]:
        """Predict acceptance probability for suggestions.
        
        Args:
            suggestions: List of suggestions with features
        
        Returns:
            List of dicts with 'accepted', 'confidence', 'uncertainty'
        """
        if not self.is_trained or not suggestions:
            # Fall back to rule-based scores
            return [
                {
                    "accepted": s.score >= self.confidence_threshold,
                    "confidence": float(s.score),
                    "uncertainty": 0.5,  # Maximum uncertainty
                    "method": "rule_based",
                }
                for s in suggestions
            ]
        
        # Extract features
        X = self._extract_feature_matrix_from_suggestions(suggestions)
        
        # Predict probabilities
        proba = self.classifier.predict_proba(X)
        
        # Get probability of positive class (accepted)
        if proba.shape[1] == 2:
            pos_proba = proba[:, 1]
        else:
            pos_proba = proba[:, 0]
        
        # Calculate uncertainty (entropy or distance from 0.5)
        uncertainty = 1.0 - 2.0 * np.abs(pos_proba - 0.5)
        
        results = []
        for i, prob in enumerate(pos_proba):
            results.append({
                "accepted": prob >= self.confidence_threshold,
                "confidence": float(prob),
                "uncertainty": float(uncertainty[i]),
                "method": "ml_trained",
            })
        
        return results
    def get_active_learning_candidates(
        self, 
        suggestions: List[PointSuggestion], 
        n: int = 5
    ) -> List[int]:
        """Get indices of most uncertain suggestions for user review.
        
        Args:
            suggestions: List of suggestions
            n: Number of candidates to return
        
        Returns:
            Indices of most uncertain suggestions
        """
        if not self.is_trained:
            # If not trained, return high-score suggestions
            scores = [s.score for s in suggestions]
            return list(np.argsort(scores)[::-1][:n])
        
        predictions = self.predict(suggestions)
        uncertainties = [p["uncertainty"] for p in predictions]
        
        # Return indices with highest uncertainty
        return list(np.argsort(uncertainties)[::-1][:n])
    def _extract_feature_matrix(self, examples: List[TrainingExample]) -> np.ndarray:
        """Extract feature matrix from training examples."""
        if not self.feature_names:
            raise ValueError("Feature names not set")
        
        X = np.zeros((len(examples), len(self.feature_names)))
        
        for i, example in enumerate(examples):
            for j, feature_name in enumerate(self.feature_names):
                X[i, j] = example.features.get(feature_name, 0.0)
        
        return X
