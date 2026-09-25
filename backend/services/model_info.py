"""
backend/services/model_info.py
==============================
Production model registry (spec §21, §22).

Loads a trained model artifact (models/reconciliation_model.json) that was
produced ONLY by scripts/train_model.py on human-verified real labels. The
registry validates the artifact (schema version, class variance, constant
prediction guard, metadata completeness) and exposes the /api/model/info
payload. If no valid artifact exists the honest status is
MODEL_UNAVAILABLE — the system runs on deterministic GIS evidence alone
and never pretends ML evidence exists.
"""

from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Any, Optional

from engine.ml_schema import FEATURE_ORDER, FEATURE_SCHEMA_VERSION

logger = logging.getLogger(__name__)

_MODELS_DIR = Path(__file__).resolve().parent.parent / "models"
ARTIFACT_PATH = _MODELS_DIR / "reconciliation_model.json"
METADATA_PATH = _MODELS_DIR / "training_metadata.json"


def _load_json(path: Path) -> Optional[dict]:
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except FileNotFoundError:
        return None
    except json.JSONDecodeError as exc:
        logger.error("Model artifact %s is corrupt: %s", path, exc)
        return {"__corrupt__": True}


def validate_artifact(artifact: Optional[dict]) -> tuple[bool, str]:
    """Validate artifact structure, schema version, and prediction variance.

    Returns (ok, reason). Guardrails (spec §22/§23):
      * artifact must exist and parse,
      * feature_schema_version must match the served code,
      * model_type must be present,
      * class distribution must not be single-class (constant predictor),
      * test metrics must exist — a model without measured held-out
        performance is not production-worthy.
    """
    if artifact is None:
        return False, "MODEL_UNAVAILABLE: no trained model artifact found"
    if artifact.get("__corrupt__"):
        return False, "MODEL_UNAVAILABLE: artifact file is corrupt"
    if artifact.get("feature_schema_version") != FEATURE_SCHEMA_VERSION:
        return (
            False,
            "MODEL_UNAVAILABLE: feature schema version mismatch "
            f"(artifact {artifact.get('feature_schema_version')} vs code {FEATURE_SCHEMA_VERSION})",
        )
    if not artifact.get("model_type"):
        return False, "MODEL_UNAVAILABLE: artifact missing model_type"
    test = artifact.get("test_metrics") or {}
    if not test.get("accuracy") and not test.get("f1_macro"):
        return False, "MODEL_UNAVAILABLE: artifact lacks held-out test metrics"
    dist = artifact.get("training_class_distribution") or {}
    if len(dist) < 2:
        return False, "MODEL_UNAVAILABLE: artifact trained on a single class (constant predictor)"
    return True, "OK"


class ModelRegistry:
    """Validated view of the current production model (or its absence)."""

    def __init__(self) -> None:
        self._artifact = _load_json(ARTIFACT_PATH)
        self._metadata = _load_json(METADATA_PATH)
        self.ok, self.reason = validate_artifact(self._artifact)
        if self.ok:
            logger.info("[model_info] Validated model artifact: %s", ARTIFACT_PATH)
        else:
            logger.info("[model_info] %s", self.reason)

    @property
    def available(self) -> bool:
        return self.ok

    def info(self) -> dict:
        """/api/model/info payload — honest in every state."""
        if not self.ok or self._artifact is None:
            return {
                "model_status": "MODEL_UNAVAILABLE",
                "reason": self.reason,
                "production_status": (
                    "Deterministic GIS evidence only. ML evidence requires a model "
                    "trained by scripts/train_model.py on human-verified real labels."
                ),
                "feature_schema_version": FEATURE_SCHEMA_VERSION,
                "feature_order": list(FEATURE_ORDER),
            }
        a = self._artifact
        return {
            "model_status": "OK",
            "model_version": a.get("model_version"),
            "model_type": a.get("model_type"),
            "training_date": a.get("training_date"),
            "training_sample_count": a.get("training_sample_count"),
            "verified_label_count": a.get("verified_label_count"),
            "verified_sample_count": a.get("verified_sample_count"),
            "class_distribution": a.get("class_distribution"),
            "feature_schema_version": a.get("feature_schema_version"),
            "feature_order": a.get("feature_order"),
            "validation_metrics": a.get("validation_metrics"),
            "test_metrics": a.get("test_metrics"),
            "final_test_metrics": a.get("test_metrics"),
            "geographic_holdout_metrics": a.get("geographic_holdout_metrics"),
            "calibration_status": a.get("calibration_status", "uncalibrated"),
            "calibration_metrics": a.get("calibration_metrics"),
            "training_class_distribution": a.get("training_class_distribution"),
            "training_data_version": a.get("training_data_version"),
            "production_status": a.get("production_status", "active"),
        }


_registry: Optional[ModelRegistry] = None


def get_registry() -> ModelRegistry:
    """Process-wide registry singleton (refreshed on each call only if absent)."""
    global _registry
    if _registry is None:
        _registry = ModelRegistry()
    return _registry


def reset_registry() -> None:
    """Reset the singleton (used by tests)."""
    global _registry
    _registry = None
