"""
ML Engine Bridge
Provides legacy get_conflict_prediction interface while routing through the
production ConflictDetectionModel service.
"""
from __future__ import annotations

from typing import Tuple
import logging
from services.ml_service import conflict_detector

logger = logging.getLogger(__name__)


def get_conflict_prediction(iou: float, area_delta: float, attr_match: float) -> Tuple[int, str]:
    """
    Predicts conflict level and provides reasoning using the centralized ML service.
    Labels: 0: No Conflict, 1: Minor, 2: Critical (-1 if unavailable/OOD)
    """
    res = conflict_detector.predict_conflict({"iou": iou, "area_delta": area_delta, "attr_match": attr_match})
    if res.get("model_status") != "OK":
        return -1, res.get("reasoning", "Model unavailable")

    return res["conflict_level"], res["reasoning"]


class ConflictModel:
    """Compatibility wrapper around production ConflictDetectionModel."""
    def __init__(self):
        self.model_service = conflict_detector

    @property
    def available(self) -> bool:
        return self.model_service.is_loaded

    def predict_conflict(self, iou: float, area_delta: float, attr_match: float) -> Tuple[int, str]:
        return get_conflict_prediction(iou, area_delta, attr_match)


_model_instance = ConflictModel()
