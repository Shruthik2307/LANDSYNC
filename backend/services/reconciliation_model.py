"""
backend/services/reconciliation_model.py
========================================
Production predictor over the validated model artifact (spec §10, §16).

Loads the fitted estimator (models/reconciliation_model.joblib) plus its
metadata (models/reconciliation_model.json — validated by model_info.py),
and predicts with explicit status:

    OK                        → prediction + probability returned
    MODEL_OUT_OF_DISTRIBUTION → no precise prediction; review required
    MODEL_UNAVAILABLE         → no artifact; deterministic evidence only

OOD detection is deterministic and documented: per-feature z-scores
against the training distribution stored in the artifact; any feature
beyond OOD_Z_THRESHOLD (or outside the training envelope) flags the input.
"""

from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Any, Optional

from engine.ml_schema import FEATURE_ORDER

logger = logging.getLogger(__name__)

_MODELS_DIR = Path(__file__).resolve().parent.parent / "models"
ESTIMATOR_PATH = _MODELS_DIR / "reconciliation_model.joblib"
ARTIFACT_PATH = _MODELS_DIR / "reconciliation_model.json"

OOD_Z_THRESHOLD = 6.0  # documented: |z| beyond this is outside training data


def _load_estimator() -> Optional[Any]:
    if not ESTIMATOR_PATH.exists():
        return None
    try:
        import joblib

        return joblib.load(ESTIMATOR_PATH)
    except Exception as exc:
        logger.error("Failed to load estimator %s: %s", ESTIMATOR_PATH, exc)
        return None


def _load_artifact() -> Optional[dict]:
    if not ARTIFACT_PATH.exists():
        return None
    try:
        with open(ARTIFACT_PATH, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception as exc:
        logger.error("Failed to load artifact %s: %s", ARTIFACT_PATH, exc)
        return None


def _is_out_of_distribution(vector: list[float], stats: dict) -> bool:
    """Deterministic OOD check: per-feature z-score vs training stats."""
    for name, value in zip(FEATURE_ORDER, vector):
        s = stats.get(name)
        if not s:
            continue
        mean, std = s.get("mean"), s.get("std")
        if std is None or std == 0:
            # Degenerate feature (constant in training): any deviation is OOD.
            if mean is not None and abs(value - mean) > 1e-9:
                return True
            continue
        z = abs(value - mean) / std
        if z > OOD_Z_THRESHOLD:
            return True
        env = s.get("min"), s.get("max")
        if env[0] is not None and env[1] is not None:
            span = env[1] - env[0]
            margin = max(0.5 * abs(span), 1e-9)
            if value < env[0] - margin or value > env[1] + margin:
                return True
    return False


class ReconciliationPredictor:
    """Stateless predictor over the validated production artifact."""

    def __init__(self) -> None:
        self.estimator = _load_estimator()
        self.artifact = _load_artifact()
        self.available = self.estimator is not None and self.artifact is not None

    def predict(self, feature_vector: list[float]) -> dict:
        """Return the ML evidence stream for fusion (spec §14/§16)."""
        if not self.available:
            return {"model_status": "MODEL_UNAVAILABLE", "prediction": None, "probability": None}
        stats = (self.artifact or {}).get("feature_stats", {})
        if _is_out_of_distribution(feature_vector, stats):
            return {
                "model_status": "MODEL_OUT_OF_DISTRIBUTION",
                "prediction": None,
                "probability": None,
                "model_version": (self.artifact or {}).get("model_version"),
            }
        try:
            pred = self.estimator.predict([feature_vector])[0]
            proba = None
            if hasattr(self.estimator, "predict_proba"):
                classes = list(self.estimator.classes_)
                probas = self.estimator.predict_proba([feature_vector])[0]
                proba = float(probas[classes.index(pred)]) if pred in classes else None
            return {
                "model_status": "OK",
                "prediction": str(pred),
                "probability": proba,
                "model_version": (self.artifact or {}).get("model_version"),
            }
        except Exception as exc:
            logger.error("Prediction failed: %s", exc)
            return {"model_status": "MODEL_UNAVAILABLE", "prediction": None, "probability": None}


_predictor: Optional[ReconciliationPredictor] = None


def get_predictor() -> ReconciliationPredictor:
    global _predictor
    if _predictor is None:
        _predictor = ReconciliationPredictor()
    return _predictor


def reset_predictor() -> None:
    global _predictor
    _predictor = None
