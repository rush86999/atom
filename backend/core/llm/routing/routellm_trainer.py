"""
RouteLLM Training Pipeline

Based on 2025-2026 research:
- "RouteLLM: Learning to Route" (arXiv:2406.18665)
- "State of AI 2025: 100T Token Study" (openrouter.ai)

Implements:
- Training pipeline for learning-based LLM routing
- Preference optimization for router
- Model evaluation and A/B testing
- Model persistence and loading
"""

import hashlib
import json
import logging
import pickle
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple
from sklearn.model_selection import train_test_split
from sklearn.ensemble import RandomForestClassifier
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import accuracy_score, classification_report
import numpy as np

logger = logging.getLogger(__name__)

# Import preference collector
try:
    from core.llm.routing.preference_collector import (
        PreferenceDataCollector,
        TrainingExample,
        FeedbackConfig,
    )
    PREFERENCE_AVAILABLE = True
except ImportError:
    logger.warning("Preference collector not available")
    PREFERENCE_AVAILABLE = False


# ============================================================================
# Enums and Configuration
# ============================================================================

class ModelType(Enum):
    """Types of routing models"""
    RANDOM_FOREST = "random_forest"
    LOGISTIC_REGRESSION = "logistic_regression"
    NEURAL_NETWORK = "neural_network"
    ENSEMBLE = "ensemble"


class TrainingStatus(Enum):
    """Status of training job"""
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


@dataclass
class TrainingConfig:
    """Configuration for router training"""
    # Model selection
    model_type: ModelType = ModelType.RANDOM_FOREST
    use_ensemble: bool = False

    # Training parameters
    test_size: float = 0.2  # Train/test split
    random_seed: int = 42
    min_samples: int = 100  # Minimum samples to train
    max_samples: int = 100000  # Maximum samples for training

    # Model hyperparameters
    n_estimators: int = 100  # For random forest
    max_depth: int = 10
    learning_rate: float = 0.001
    epochs: int = 10

    # Evaluation
    min_accuracy: float = 0.7  # Minimum accuracy to deploy
    cross_validation: bool = True
    cv_folds: int = 5

    # Persistence
    model_path: str = "data/router_models"
    model_version: str = "latest"

    # A/B testing
    ab_test_confidence: float = 0.95  # Confidence threshold for A/B test
    min_ab_samples: int = 100  # Minimum samples for A/B test


@dataclass
class TrainingResult:
    """Result of training process"""
    status: TrainingStatus = TrainingStatus.PENDING
    model_id: str = ""
    accuracy: float = 0.0
    precision: float = 0.0
    recall: float = 0.0
    f1_score: float = 0.0
    confusion_matrix: Optional[np.ndarray] = None
    training_time_ms: float = 0.0
    samples_trained: int = 0
    metadata: Dict[str, Any] = field(default_factory=dict)


# ============================================================================
# Feature Extractor
# ============================================================================

class FeatureExtractor:
    """Extract features from training examples for model training"""

    def __init__(self):
        """Initialize feature extractor"""
        self.feature_names = [
            "log_tokens",
            "token_bucket",
            "task_code",
            "task_analysis",
            "task_reasoning",
            "task_chat",
            "task_general",
            "has_code",
            "has_numbers",
            "avg_word_length",
        ]

    def extract_features(self, examples: List[TrainingExample]) -> np.ndarray:
        """
        Extract feature matrix from training examples.

        Args:
            examples: List of training examples

        Returns:
            Feature matrix X of shape (n_samples, n_features)
        """
        if not examples:
            return np.array([])

        features = []
        for example in examples:
            feature_vector = [
                example.prompt_features.get("log_tokens", 0),
                example.prompt_features.get("token_bucket", 0),
                example.prompt_features.get("task_code", 0),
                example.prompt_features.get("task_analysis", 0),
                example.prompt_features.get("task_reasoning", 0),
                example.prompt_features.get("task_chat", 0),
                example.prompt_features.get("task_general", 0),
                example.prompt_features.get("has_code", 0),
                example.prompt_features.get("has_numbers", 0),
                example.prompt_features.get("avg_word_length", 0),
            ]
            features.append(feature_vector)

        return np.array(features)

    def extract_targets(self, examples: List[TrainingExample]) -> np.ndarray:
        """
        Extract target labels from training examples.

        Args:
            examples: List of training examples

        Returns:
            Target vector y (binary satisfaction)
        """
        if not examples:
            return np.array([])

        targets = []
        for example in examples:
            # Binary target: satisfied (1) or not (0)
            satisfied = 1.0 if example.user_satisfaction >= 0.5 else 0.0
            targets.append(satisfied)

        return np.array(targets)

    def extract_weights(self, examples: List[TrainingExample]) -> np.ndarray:
        """Extract sample weights for training"""
        if not examples:
            return np.ones(0)

        return np.array([e.weight for e in examples])


# ============================================================================
# RouteLLM Trainer
# ============================================================================

class RouteLLMTrainer:
    """
    Training pipeline for learning-based LLM router.

    Features:
    - Multiple model types (Random Forest, Logistic Regression, Ensemble)
    - Feature extraction from preference data
    - Train/test split with proper evaluation
    - Model persistence and loading
    - A/B test support
    """

    def __init__(self, config: Optional[TrainingConfig] = None):
        self.config = config or TrainingConfig()
        self.feature_extractor = FeatureExtractor()
        self.model = None
        self.model_metadata = {}

        # Create model directory
        Path(self.config.model_path).mkdir(parents=True, exist_ok=True)

    def train(
        self,
        examples: List[TrainingExample],
        model_id: Optional[str] = None
    ) -> TrainingResult:
        """
        Train routing model from preference data.

        Args:
            examples: List of training examples
            model_id: Optional model identifier

        Returns:
            TrainingResult with metrics
        """
        start_time = datetime.now()

        if not PREFERENCE_AVAILABLE:
            return TrainingResult(
                status=TrainingStatus.FAILED,
                metadata={"error": "Preference collector not available"}
            )

        if len(examples) < self.config.min_samples:
            return TrainingResult(
                status=TrainingStatus.FAILED,
                metadata={
                    "error": f"Insufficient samples: {len(examples)} < {self.config.min_samples}"
                }
            )

        result = TrainingResult(status=TrainingStatus.RUNNING)
        result.model_id = model_id or self._generate_model_id()

        try:
            # Extract features and targets
            X = self.feature_extractor.extract_features(examples)
            y = self.feature_extractor.extract_targets(examples)
            weights = self.feature_extractor.extract_weights(examples)

            if len(X) == 0 or len(y) == 0:
                raise ValueError("No features extracted from examples")

            # Train/test split
            X_train, X_test, y_train, y_test = train_test_split(
                X, y,
                test_size=self.config.test_size,
                random_state=self.config.random_seed,
                stratify=y if len(np.unique(y)) > 1 else None
            )

            # Train model
            self.model = self._create_model()
            self.model.fit(X_train, y_train, sample_weight=weights[:len(X_train)])

            # Evaluate
            y_pred = self.model.predict(X_test)
            accuracy = accuracy_score(y_test, y_pred)

            # Build result
            result.status = TrainingStatus.COMPLETED
            result.accuracy = accuracy
            result.samples_trained = len(examples)
            result.training_time_ms = (datetime.now() - start_time).total_seconds() * 1000

            # Additional metrics
            from sklearn.metrics import precision_score, recall_score, f1_score
            try:
                result.precision = precision_score(y_test, y_pred)
                result.recall = recall_score(y_test, y_pred)
                result.f1_score = f1_score(y_test, y_pred)
            except Exception as e:
                logger.warning(f"Could not calculate precision/recall: {e}")

            # Save model
            self._save_model(result.model_id)

            result.metadata = {
                "model_type": self.config.model_type.value,
                "trained_at": datetime.now().isoformat(),
                "feature_importance": self._get_feature_importance(),
            }

            logger.info(
                f"Training completed: model={result.model_id}, "
                f"accuracy={accuracy:.3f}, samples={len(examples)}"
            )

        except Exception as e:
            logger.error(f"Training failed: {e}")
            result.status = TrainingStatus.FAILED
            result.metadata["error"] = str(e)

        return result

    def _create_model(self):
        """Create model instance based on configuration"""
        if self.config.model_type == ModelType.RANDOM_FOREST:
            return RandomForestClassifier(
                n_estimators=self.config.n_estimators,
                max_depth=self.config.max_depth,
                random_state=self.config.random_seed,
                n_jobs=-1  # Use all cores
            )
        elif self.config.model_type == ModelType.LOGISTIC_REGRESSION:
            return LogisticRegression(
                random_state=self.config.random_seed,
                max_iter=1000
            )
        else:
            raise ValueError(f"Unsupported model type: {self.config.model_type}")

    def _save_model(self, model_id: str) -> None:
        """Save trained model to disk"""
        if self.model is None:
            return

        model_file = Path(self.config.model_path) / f"{model_id}.pkl"
        with open(model_file, 'wb') as f:
            pickle.dump(self.model, f)

        logger.info(f"Model saved to {model_file}")

    def load_model(self, model_id: str) -> bool:
        """Load trained model from disk"""
        model_file = Path(self.config.model_path) / f"{model_id}.pkl"

        if not model_file.exists():
            logger.warning(f"Model file not found: {model_file}")
            return False

        try:
            with open(model_file, 'rb') as f:
                self.model = pickle.load(f)

            logger.info(f"Model loaded from {model_file}")
            return True
        except Exception as e:
            logger.error(f"Failed to load model: {e}")
            return False

    def predict(self, features: Dict[str, float]) -> float:
        """
        Predict satisfaction score for routing decision.

        Args:
            features: Feature dictionary

        Returns:
            Predicted satisfaction score (0-1)
        """
        if self.model is None:
            return 0.5  # Default uncertainty

        # Convert features to vector
        feature_vector = np.array([
            features.get(name, 0.0)
            for name in self.feature_extractor.feature_names
        ]).reshape(1, -1)

        # Predict probability of satisfaction
        if hasattr(self.model, 'predict_proba'):
            proba = self.model.predict_proba(feature_vector)
            return proba[0][1] if proba.shape[1] > 1 else proba[0][0]
        else:
            prediction = self.model.predict(feature_vector)
            return float(prediction[0])

    def get_best_model(
        self,
        examples: List[TrainingExample],
        model_types: Optional[List[ModelType]] = None
    ) -> Tuple[ModelType, TrainingResult]:
        """
        Find best model type through evaluation.

        Args:
            examples: Training examples
            model_types: Optional list of model types to evaluate

        Returns:
            Tuple of (best_model_type, best_result)
        """
        model_types = model_types or [
            ModelType.RANDOM_FOREST,
            ModelType.LOGISTIC_REGRESSION
        ]

        best_model = None
        best_score = -1
        best_result = None

        for model_type in model_types:
            # Temporarily change config
            original_type = self.config.model_type
            self.config.model_type = model_type

            result = self.train(examples)

            # Restore original config
            self.config.model_type = original_type

            if result.accuracy > best_score:
                best_score = result.accuracy
                best_model = model_type
                best_result = result

        return best_model, best_result

    def _generate_model_id(self) -> str:
        """Generate unique model identifier"""
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        hash_val = hashlib.md5(timestamp.encode()).hexdigest()[:8]
        return f"model_{timestamp}_{hash_val}"

    def _get_feature_importance(self) -> Dict[str, float]:
        """Get feature importance from trained model"""
        if self.model is None or not hasattr(self.model, 'feature_importances_'):
            return {}

        importance_dict = {}
        for name, importance in zip(self.feature_extractor.feature_names, self.model.feature_importances_):
            importance_dict[name] = float(importance)

        return importance_dict


# ============================================================================
# Router Evaluator
# ============================================================================

class RouterEvaluator:
    """Evaluator for comparing router performance"""

    def __init__(self, config: Optional[TrainingConfig] = None):
        self.config = config or TrainingConfig()

    def evaluate_ab_test(
        self,
        control_outcomes: List[float],
        learning_outcomes: List[float]
    ) -> Dict[str, Any]:
        """
        Evaluate A/B test results between control and learning routers.

        Args:
            control_outcomes: Satisfaction scores from control group
            learning_outcomes: Satisfaction scores from learning group

        Returns:
            Evaluation metrics
        """
        from scipy import stats

        # Calculate metrics
        control_mean = np.mean(control_outcomes) if control_outcomes else 0
        learning_mean = np.mean(learning_outcomes) if learning_outcomes else 0
        improvement = learning_mean - control_mean

        # Statistical test
        if len(control_outcomes) >= 30 and len(learning_outcomes) >= 30:
            t_stat, p_value = stats.ttest_ind(learning_outcomes, control_outcomes)
            significant = p_value < (1 - self.config.ab_test_confidence)
        else:
            t_stat = 0
            p_value = 1.0
            significant = False

        return {
            "control_mean": round(control_mean, 3),
            "learning_mean": round(learning_mean, 3),
            "improvement": round(improvement, 3),
            "improvement_percent": round(improvement / max(control_mean, 0.001) * 100, 1),
            "t_statistic": round(t_stat, 3),
            "p_value": round(p_value, 3),
            "significant": significant,
            "control_samples": len(control_outcomes),
            "learning_samples": len(learning_outcomes),
        }

    def get_confidence_interval(
        self,
        data: List[float],
        confidence: float = 0.95
    ) -> Tuple[float, float]:
        """
        Calculate confidence interval for mean.

        Args:
            data: Data points
            confidence: Confidence level (0-1)

        Returns:
            (lower_bound, upper_bound)
        """
        if len(data) < 2:
            return (0.0, 1.0)

        import scipy.stats as stats
        mean = np.mean(data)
        stderr = stats.sem(data)
        h = stderr * stats.t.ppf((1 + confidence) / 2, len(data) - 1)

        return (mean - h, mean + h)


# ============================================================================
# Factory
# ============================================================================

def get_router_trainer(config: Optional[TrainingConfig] = None) -> RouteLLMTrainer:
    """Factory function to get router trainer instance"""
    return RouteLLMTrainer(config)


def get_router_evaluator(config: Optional[TrainingConfig] = None) -> RouterEvaluator:
    """Factory function to get router evaluator instance"""
    return RouterEvaluator(config)
