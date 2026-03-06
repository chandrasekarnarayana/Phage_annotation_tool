"""Interactive learning model inspired by Weka Trainable Segmentation.

Instead of a 2-step pipeline (rule-based → offline ML), this implements:
- Single integrated system that learns from user feedback
- Real-time model updates as user accepts/rejects suggestions
- Model persistence per experiment type
- Active learning to suggest most uncertain examples
"""

from __future__ import annotations

import pickle
from dataclasses import dataclass, field
from pathlib import Path
from typing import List, Literal, Optional

import numpy as np

from phage_annotator.core.annotation import PointSuggestion


@dataclass
class TrainingExample:
    """Single training example with features and label."""
    
    suggestion_id: str
    features: dict[str, float]
    label: int  # 1 = accepted, 0 = rejected
    image_name: str
    t: int
    z: int


@dataclass
class InteractiveLearningModel:
    """Weka-inspired interactive learning for keypoint detection.
    
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
    
    def _extract_feature_matrix_from_suggestions(
        self, 
        suggestions: List[PointSuggestion]
    ) -> np.ndarray:
        """Extract feature matrix from suggestions."""
        if not self.feature_names:
            # Use all features from first suggestion
            if suggestions:
                self.feature_names = sorted(suggestions[0].score_components.keys())
            else:
                return np.zeros((0, 0))
        
        X = np.zeros((len(suggestions), len(self.feature_names)))
        
        for i, suggestion in enumerate(suggestions):
            for j, feature_name in enumerate(self.feature_names):
                X[i, j] = suggestion.score_components.get(feature_name, 0.0)
        
        return X
    
    def save(self, path: str | Path) -> None:
        """Save model to disk."""
        path = Path(path)
        path.parent.mkdir(parents=True, exist_ok=True)
        
        state = {
            "model_type": self.model_type,
            "classifier": self.classifier,
            "feature_names": self.feature_names,
            "training_examples": self.training_examples,
            "is_trained": self.is_trained,
            "model_version": self.model_version,
            "n_accepted": self.n_accepted,
            "n_rejected": self.n_rejected,
            "last_accuracy": self.last_accuracy,
            "update_frequency": self.update_frequency,
            "min_examples_to_train": self.min_examples_to_train,
            "confidence_threshold": self.confidence_threshold,
        }
        
        with open(path, "wb") as f:
            pickle.dump(state, f)
    
    @classmethod
    def load(cls, path: str | Path) -> InteractiveLearningModel:
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
