"""
Per-model satisfaction predictors for learning-based LLM routing.

The original ``RouteLLMTrainer`` trains a single classifier that predicts
user satisfaction from prompt features. Because *model identity* is not one of
its features, that model cannot learn which model to pick — it only learns
"do prompts like this tend to satisfy users?".

``PerModelRouter`` closes that gap by holding one small sklearn estimator per
model. Model identity enters routing through **which predictor you query**, not
through a feature: each predictor learns "for *this* model, do prompts like
this satisfy users?". At route time the router asks each candidate model's
predictor for a satisfaction probability and boosts models that historically
deliver satisfaction.

All training and inference is CPU-only scikit-learn (RandomForest /
LogisticRegression). A typical predictor is a small RandomForest fit on tens
to a few hundred examples with 10 features — a sub-10ms job that runs on any
end-user laptop.

Known limitation: today ``RoutingFeedback`` carries no prompt text, so all
feedback for a given tenant/task yields near-identical features (only the
target varies). Each predictor therefore mostly learns a model's *average*
satisfaction for that task — still a real per-model quality signal, and the
architecture is ready to exploit richer prompt features the moment feedback
captures them.
"""

from __future__ import annotations

import json
import logging
import pickle
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import numpy as np

from core.llm.routing.routellm_trainer import (
    FeatureExtractor,
    ModelType,
    TrainingConfig,
    TrainingResult,
    TrainingStatus,
)
from core.llm.routing.preference_collector import TrainingExample

logger = logging.getLogger(__name__)


@dataclass
class PredictorStats:
    """Metadata about a trained per-model predictor."""

    model_id: str
    samples: int = 0
    accuracy: float = 0.0
    trained_at: str = ""
    positive_rate: float = 0.5  # fraction of satisfied examples seen
    classes: List[int] = field(default_factory=list)


class PerModelRouter:
    """Holds one sklearn satisfaction predictor per model id.

    Each predictor answers: "given these prompt features, what is the
    probability that *this* model satisfies the user?" The router queries the
    predictor belonging to each candidate model and boosts models with higher
    predicted satisfaction.
    """

    def __init__(self, config: Optional[TrainingConfig] = None):
        self.config = config or TrainingConfig()
        self.feature_extractor = FeatureExtractor()
        # model_id -> fitted sklearn estimator
        self.predictors: Dict[str, Any] = {}
        # model_id -> stats about the last training run
        self.stats: Dict[str, PredictorStats] = {}
        self._model_dir = Path(self.config.model_path) / "per_model"
        self._model_dir.mkdir(parents=True, exist_ok=True)

    # ------------------------------------------------------------------
    # Training
    # ------------------------------------------------------------------
    def train(
        self,
        model_id: str,
        examples: List[TrainingExample],
    ) -> TrainingResult:
        """Train (or retrain) the predictor for ``model_id``.

        Args:
            model_id: The model whose satisfaction this predictor estimates.
            examples: Feedback-derived training examples for this model.

        Returns:
            A ``TrainingResult`` describing the fit. ``COMPLETED`` predictors
            are immediately queryable via :meth:`predict_satisfaction`.
        """
        start = datetime.now()
        result = TrainingResult(status=TrainingStatus.RUNNING)
        result.model_id = f"per_model_{model_id}"

        try:
            X = self.feature_extractor.extract_features(examples)
            y = self.feature_extractor.extract_targets(examples)

            if len(X) == 0 or len(y) == 0:
                raise ValueError("No features extracted from examples")

            unique_classes = np.unique(y)
            if len(unique_classes) < 2:
                # Single-class data: nothing to learn; remember the constant
                # so predict_satisfaction can return the observed rate without
                # inventing a classifier.
                positive_rate = float(unique_classes[0]) if len(unique_classes) else 0.5
                estimator = None
                accuracy = positive_rate
            else:
                estimator = self._create_estimator()
                estimator.fit(X, y)
                # Training accuracy on the full set (these predictors are tiny;
                # a held-out split on ~20-100 examples is too noisy to be
                # meaningful, so we report in-sample fit as a rough confidence
                # signal rather than a generalization guarantee).
                accuracy = float(estimator.score(X, y))

            self.predictors[model_id] = estimator
            positive_rate = float(np.mean(y)) if len(y) else 0.5
            self.stats[model_id] = PredictorStats(
                model_id=model_id,
                samples=len(examples),
                accuracy=accuracy,
                trained_at=datetime.now().isoformat(),
                positive_rate=positive_rate,
                classes=[int(c) for c in unique_classes],
            )

            result.status = TrainingStatus.COMPLETED
            result.accuracy = accuracy
            result.samples_trained = len(examples)
            result.training_time_ms = (datetime.now() - start).total_seconds() * 1000
            result.metadata = {
                "model_id": model_id,
                "accuracy": accuracy,
                "samples": len(examples),
                "positive_rate": positive_rate,
            }

            self._save_predictor(model_id)

            logger.info(
                f"Trained per-model predictor for {model_id}: "
                f"samples={len(examples)}, accuracy={accuracy:.3f}"
            )
        except Exception as e:
            logger.error(f"Per-model training failed for {model_id}: {e}")
            result.status = TrainingStatus.FAILED
            result.metadata["error"] = str(e)

        return result

    def _create_estimator(self):
        """Build the sklearn estimator (mirrors RouteLLMTrainer defaults).

        Defaults to RandomForest — robust on small tabular data, no scaling.
        Supports LOGISTIC_REGRESSION, NEURAL_NETWORK (small MLP), and ENSEMBLE
        (soft-vote RF+LR). All CPU-only.
        """
        if self.config.model_type == ModelType.LOGISTIC_REGRESSION:
            from sklearn.linear_model import LogisticRegression
            return LogisticRegression(
                random_state=self.config.random_seed, max_iter=1000
            )
        if self.config.model_type == ModelType.NEURAL_NETWORK:
            from sklearn.neural_network import MLPClassifier
            return MLPClassifier(
                hidden_layer_sizes=(64, 32),
                learning_rate_init=self.config.learning_rate,
                max_iter=self.config.epochs,
                random_state=self.config.random_seed,
            )
        if self.config.model_type == ModelType.ENSEMBLE:
            from sklearn.ensemble import (
                RandomForestClassifier, VotingClassifier,
            )
            from sklearn.linear_model import LogisticRegression
            return VotingClassifier(
                estimators=[
                    ("rf", RandomForestClassifier(
                        n_estimators=self.config.n_estimators,
                        max_depth=self.config.max_depth,
                        random_state=self.config.random_seed,
                        n_jobs=-1,
                    )),
                    ("lr", LogisticRegression(
                        random_state=self.config.random_seed,
                        max_iter=1000,
                    )),
                ],
                voting="soft",
            )
        # Default to RandomForest — robust on small tabular data, no scaling.
        from sklearn.ensemble import RandomForestClassifier
        return RandomForestClassifier(
            n_estimators=self.config.n_estimators,
            max_depth=self.config.max_depth,
            random_state=self.config.random_seed,
            n_jobs=-1,
        )

    # ------------------------------------------------------------------
    # Inference
    # ------------------------------------------------------------------
    def predict_satisfaction(
        self, model_id: str, features: Dict[str, float]
    ) -> Optional[float]:
        """Predict P(satisfaction) for ``model_id`` given prompt features.

        Returns ``None`` when no predictor exists for the model (cold start —
        the caller should fall back to the rule-based score). For a trained
        predictor returns a float in [0, 1].
        """
        if model_id not in self.stats:
            return None

        stats = self.stats[model_id]
        estimator = self.predictors.get(model_id)

        # Single-class predictor: return the observed satisfaction rate.
        if estimator is None:
            return stats.positive_rate

        vector = np.array([
            features.get(name, 0.0)
            for name in self.feature_extractor.feature_names
        ]).reshape(1, -1)

        if hasattr(estimator, "predict_proba"):
            proba = estimator.predict_proba(vector)[0]
            # Map probability back to P(class==1). classes_ tells us the column
            # ordering even when the estimator saw an unbalanced class set.
            classes = list(estimator.classes_)
            if 1 in classes:
                return float(proba[classes.index(1)])
            # No positive class seen at training time.
            return 0.0
        return float(estimator.predict(vector)[0])

    def has_predictor(self, model_id: str) -> bool:
        return model_id in self.stats

    def predictor_stats(self, model_id: str) -> Optional[PredictorStats]:
        return self.stats.get(model_id)

    def confidence(self, model_id: str, max_weight: float = 0.3) -> float:
        """A 0..max_weight blend weight for the learned signal.

        Scales with how much we trust this predictor: more samples → more
        trust, capped at ``max_weight`` so the rule-based score always
        contributes the majority of the decision. This keeps early noisy
        predictors from dominating while letting a well-trained predictor
        meaningfully steer routing.
        """
        stats = self.stats.get(model_id)
        if stats is None:
            return 0.0
        # Reach ~full weight at 50 samples; half weight at ~12.
        return min(max_weight, max_weight * (stats.samples / 50.0))

    # ------------------------------------------------------------------
    # Persistence
    # ------------------------------------------------------------------
    def _save_predictor(self, model_id: str) -> None:
        """Persist a predictor + its stats to disk."""
        safe_id = model_id.replace("/", "_").replace("\\", "_").replace("..", "_")
        base = self._model_dir.resolve()
        pkl_path = (base / f"{safe_id}.pkl").resolve()
        meta_path = (base / f"{safe_id}.json").resolve()
        # Path-traversal containment.
        try:
            pkl_path.relative_to(base)
        except ValueError:
            raise ValueError(f"Model id '{model_id}' resolves outside model dir")

        stats = self.stats[model_id]
        estimator = self.predictors.get(model_id)
        with open(pkl_path, "wb") as f:
            pickle.dump(estimator, f)  # estimator may be None (single-class)
        with open(meta_path, "w") as f:
            json.dump(
                {
                    "model_id": stats.model_id,
                    "samples": stats.samples,
                    "accuracy": stats.accuracy,
                    "trained_at": stats.trained_at,
                    "positive_rate": stats.positive_rate,
                    "classes": stats.classes,
                },
                f,
            )

    def load_all(self) -> int:
        """Load every persisted predictor in the model dir.

        Returns the number of predictors loaded. Safe to call at startup; a
        missing/empty dir loads zero predictors (clean cold start).
        """
        loaded = 0
        for meta_path in self._model_dir.glob("*.json"):
            try:
                with open(meta_path) as f:
                    meta = json.load(f)
                model_id = meta["model_id"]
                pkl_path = meta_path.with_suffix(".pkl")
                estimator = None
                if pkl_path.exists():
                    with open(pkl_path, "rb") as f:
                        estimator = pickle.load(f)
                self.predictors[model_id] = estimator
                self.stats[model_id] = PredictorStats(
                    model_id=model_id,
                    samples=meta.get("samples", 0),
                    accuracy=meta.get("accuracy", 0.0),
                    trained_at=meta.get("trained_at", ""),
                    positive_rate=meta.get("positive_rate", 0.5),
                    classes=meta.get("classes", []),
                )
                loaded += 1
            except Exception as e:
                logger.warning(f"Could not load predictor {meta_path}: {e}")
        if loaded:
            logger.info(f"Loaded {loaded} per-model predictors from {self._model_dir}")
        return loaded


def get_per_model_router(config: Optional[TrainingConfig] = None) -> PerModelRouter:
    """Factory for a PerModelRouter."""
    return PerModelRouter(config)
