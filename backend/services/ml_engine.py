import pickle
import numpy as np
from pathlib import Path
from typing import Any, Dict, Tuple
import logging

logger = logging.getLogger(__name__)

MODEL_PATH = Path(__file__).resolve().parent.parent / "models" / "conflict_detector.pkl"

class ConflictModel:
    def __init__(self):
        try:
            with open(MODEL_PATH, "rb") as f:
                self.model = pickle.load(f)
            self.available = True
        except Exception as e:
            logger.error("Failed to load ML model: %s", e)
            self.available = False

    def predict_conflict(self, iou: float, area_delta: float, attr_match: float) -> Tuple[int, str]:
        """
        Predicts conflict level and provides reasoning.
        Labels: 0: No Conflict, 1: Minor, 2: Critical
        """
        if not self.available:
            return -1, "Model unavailable"

        features = np.array([[iou, area_delta, attr_match]])
        prediction = int(self.model.predict(features)[0])

        # Generate Reasoning (XAI)
        reasons = []
        if iou < 0.5: reasons.append(f"Low spatial overlap (IoU: {iou:.2f})")
        if area_delta > 0.3: reasons.append(f"Significant area discrepancy (Delta: {area_delta:.2f})")
        if attr_match < 0.6: reasons.append(f"Attribute mismatch (Match: {attr_match:.2f})")

        reasoning = " | ".join(reasons) if reasons else "All metrics within normal bounds"

        mapping = {0: "No Conflict", 1: "Minor Conflict", 2: "Critical Conflict"}
        return prediction, f"{mapping[prediction]} - {reasoning}"

# Singleton
_model_instance = ConflictModel()

def get_conflict_prediction(iou: float, area_delta: float, attr_match: float):
    return _model_instance.predict_conflict(iou, area_delta, attr_match)
