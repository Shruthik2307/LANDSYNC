"""
ML-Based Conflict Detection Engine
Confidence scoring, topology validation, and AI-powered conflict detection.
Consumes real GIS reconciliation metrics from the authoritative geometric engine.
"""
from __future__ import annotations

import logging
from pathlib import Path
import pickle
from typing import Any, Dict, List, Optional, Tuple

import numpy as np
import pandas as pd
from sklearn.ensemble import GradientBoostingRegressor, RandomForestClassifier
from sklearn.model_selection import train_test_split
from sklearn.preprocessing import StandardScaler
from sklearn.utils.validation import check_is_fitted, NotFittedError

from engine.ml_schema import FEATURE_ORDER, FEATURE_SCHEMA_VERSION

logger = logging.getLogger(__name__)


class MLPredictionResult(dict):
    """
    Rich prediction result dictionary that also supports legacy 2-tuple unpacking:
    `has_conflict, confidence = result`
    """
    def __iter__(self):
        yield self.get("has_conflict", False)
        yield self.get("confidence", 0.0)

    def __getitem__(self, key: Any) -> Any:
        if isinstance(key, int):
            if key == 0:
                return self.get("has_conflict", False)
            elif key == 1:
                return self.get("confidence", 0.0)
            raise IndexError("MLPredictionResult tuple index out of range (0 or 1)")
        return super().__getitem__(key)


class ConflictDetectionModel:
    """Production ML model for detecting, classifying, and scoring geospatial conflicts."""

    def __init__(self, model_path: Optional[Any] = None):
        if model_path is not None:
            self.model_path = Path(model_path)
        else:
            self.model_path = Path(__file__).resolve().parent.parent / "models" / "conflict_detector.pkl"
        self.classifier: Optional[Any] = None
        self.confidence_model: Optional[Any] = None
        self.scaler: Optional[Any] = None
        self.feature_names: List[str] = ["iou", "area_delta", "attr_match"]
        self.feature_schema_version: str = FEATURE_SCHEMA_VERSION
        self.model_version: str = "1.0.0"
        self.is_loaded: bool = False
        self.load_status: str = "UNINITIALIZED"

        if self.model_path.exists():
            self.load_model()
        else:
            self.load_status = "MODEL_UNAVAILABLE: model file does not exist"

    def load_model(self) -> bool:
        """
        Load trained model from disk, supporting both dictionary and raw estimator formats.
        Performs fittedness and variance verification to reject constant predictors.
        """
        try:
            if not self.model_path.exists():
                self.is_loaded = False
                self.load_status = "MODEL_UNAVAILABLE: model file not found"
                return False

            with open(self.model_path, "rb") as f:
                data = pickle.load(f)

            classifier = None
            confidence_model = None
            scaler = None
            feature_names = None

            if isinstance(data, dict):
                classifier = data.get("classifier") or data.get("model")
                confidence_model = data.get("confidence_model")
                scaler = data.get("scaler")
                feature_names = data.get("feature_names")
                self.model_version = data.get("model_version", self.model_version)
            elif hasattr(data, "predict"):
                classifier = data

            if classifier is None:
                logger.warning("Artifact at %s contains no valid classifier", self.model_path)
                self.is_loaded = False
                self.load_status = "MODEL_UNAVAILABLE: artifact lacks classifier"
                return False

            # Verify that classifier is fitted
            try:
                check_is_fitted(classifier)
            except (NotFittedError, TypeError, ValueError) as exc:
                logger.warning("Classifier at %s is not fitted: %s", self.model_path, exc)
                self.is_loaded = False
                self.load_status = "MODEL_UNAVAILABLE: classifier is not fitted"
                return False

            # Verify multi-class variance
            classes = getattr(classifier, "classes_", None)
            if classes is None or len(classes) < 2:
                logger.warning("Model at %s has fewer than 2 classes (constant predictor)", self.model_path)
                self.is_loaded = False
                self.load_status = "MODEL_UNAVAILABLE: single-class constant predictor"
                return False

            # Determine feature schema expected by the model
            if feature_names is not None:
                self.feature_names = list(feature_names)
            elif hasattr(classifier, "feature_names_in_") and classifier.feature_names_in_ is not None:
                self.feature_names = list(classifier.feature_names_in_)
            elif getattr(classifier, "n_features_in_", None) == 3:
                self.feature_names = ["iou", "area_delta", "attr_match"]
            elif getattr(classifier, "n_features_in_", None) == len(FEATURE_ORDER):
                self.feature_names = list(FEATURE_ORDER)

            self.classifier = classifier
            self.confidence_model = confidence_model
            self.scaler = scaler

            # Verify variance on sample inputs
            if not self._verify_model_variance():
                logger.warning("Model at %s failed variance check (constant output)", self.model_path)
                self.is_loaded = False
                self.load_status = "MODEL_UNAVAILABLE: constant predictor on distinct inputs"
                return False

            self.is_loaded = True
            self.load_status = "OK"
            logger.info("ConflictDetectionModel loaded and verified from %s with %d features", self.model_path, len(self.feature_names))
            return True

        except Exception as e:
            logger.warning("Failed to load model from %s: %s", self.model_path, e)
            self.is_loaded = False
            self.load_status = f"MODEL_UNAVAILABLE: load exception ({e})"
            return False

    def _verify_model_variance(self) -> bool:
        """Verify model produces different outputs for distinct inputs."""
        try:
            if self.classifier is None or not hasattr(self.classifier, "predict"):
                return False

            n_feats = len(self.feature_names)
            # Input 1: clear match (high IoU, low delta, high match)
            # Input 2: critical conflict (low IoU, high delta, low match)
            if n_feats == 3:
                x_test = pd.DataFrame(
                    [[0.95, 0.02, 1.0], [0.10, 0.85, 0.0]],
                    columns=self.feature_names,
                )
            else:
                x_test = pd.DataFrame(
                    [
                        [1.0] * n_feats,
                        [0.0] * n_feats,
                    ],
                    columns=self.feature_names,
                )

            if self.scaler is not None and hasattr(self.scaler, "transform"):
                x_test_in = self.scaler.transform(x_test)
            else:
                x_test_in = x_test

            preds = self.classifier.predict(x_test_in)
            return len(np.unique(preds)) > 1
        except Exception as exc:
            logger.warning("Variance check failed: %s", exc)
            return False

    def extract_features_dict(self, data: Any) -> Dict[str, float]:
        """
        Extract canonical and model-specific features from real GIS reconciliation data.
        Handles engine pair metrics, parcel records, feature vectors, or legacy dicts.
        """
        if isinstance(data, (list, tuple, np.ndarray)):
            # 14-element canonical vector or 3-element vector
            vec = list(data)
            if len(vec) == len(FEATURE_ORDER):
                raw = {k: (float(v) if v is not None else 0.0) for k, v in zip(FEATURE_ORDER, vec)}
                iou = raw.get("iou", 0.0)
                area_ratio = raw.get("area_ratio", 1.0)
                area_delta = max(0.0, min(1.0, 1.0 - area_ratio)) if area_ratio is not None else 0.0
                survey_m = raw.get("survey_number_match", 1.0)
                land_m = raw.get("land_use_match", 1.0)
                class_m = raw.get("classification_match", 1.0)
                attr_match = float(np.mean([m for m in (survey_m, land_m, class_m) if m is not None])) if any(m is not None for m in (survey_m, land_m, class_m)) else 1.0
                raw["area_delta"] = area_delta
                raw["attr_match"] = attr_match
                return raw
            elif len(vec) == 3:
                return {
                    "iou": float(vec[0]) if vec[0] is not None else 0.0,
                    "area_delta": float(vec[1]) if vec[1] is not None else 0.0,
                    "attr_match": float(vec[2]) if vec[2] is not None else 0.0,
                }

        d = data if isinstance(data, dict) else {}
        sm = d.get("spatial_metrics") if isinstance(d.get("spatial_metrics"), dict) else {}
        am = d.get("attribute_metrics") if isinstance(d.get("attribute_metrics"), dict) else {}

        # 1. Spatial IoU
        iou = sm.get("iou")
        if iou is None:
            iou = d.get("iou_score", d.get("iou", 0.0))
        iou = float(np.clip(iou, 0.0, 1.0)) if iou is not None else 0.0

        # 2. Area metrics
        area_ratio = sm.get("area_ratio")
        if area_ratio is None:
            area_ratio = d.get("area_ratio")
        if area_ratio is None and "area_delta" in d:
            area_ratio = max(0.0, 1.0 - float(d["area_delta"]))
        if area_ratio is None:
            area_ratio = 1.0
        area_ratio = float(np.clip(area_ratio, 0.0, 1.0))

        area_delta = d.get("area_delta")
        if area_delta is None:
            area_delta = 1.0 - area_ratio
        area_delta = float(np.clip(area_delta, 0.0, 1.0))

        area_diff_m2 = sm.get("area_difference_m2")
        if area_diff_m2 is None:
            area_diff_m2 = d.get("area_difference")
        if area_diff_m2 is None:
            area_diff_m2 = area_delta * 1000.0 if area_delta > 0 else 0.0
        area_diff_m2 = max(0.0, float(area_diff_m2))

        # 3. Centroid & Boundary distances
        centroid_d = sm.get("centroid_distance_m")
        if centroid_d is None:
            centroid_d = d.get("centroid_distance")
        if centroid_d is None:
            centroid_d = (1.0 - iou) * 40.0
        centroid_d = max(0.0, float(centroid_d))

        hausdorff_d = sm.get("hausdorff_distance_m", d.get("hausdorff_distance_m"))
        if hausdorff_d is None:
            hausdorff_d = (1.0 - iou) * 100.0
        hausdorff_d = max(0.0, float(hausdorff_d))

        boundary_disp = sm.get("boundary_displacement_m", d.get("boundary_displacement_m"))
        if boundary_disp is None:
            boundary_disp = (1.0 - iou) * 40.0
        boundary_disp = max(0.0, float(boundary_disp))

        shape_sim = sm.get("shape_similarity", d.get("shape_similarity"))
        if shape_sim is None:
            shape_sim = iou
        shape_sim = float(np.clip(shape_sim, 0.0, 1.0))

        overlap_pct = sm.get("overlap_pct_of_cadastral", d.get("overlap_pct_of_cadastral", iou * 100.0))
        compactness_diff = sm.get("compactness_difference", d.get("compactness_difference", 0.0))
        perimeter_diff_m = sm.get("perimeter_difference_m", d.get("perimeter_difference_m", 0.0))
        vertex_count_diff = sm.get("vertex_count_diff", d.get("vertex_count_diff", 0))

        # 4. Attribute matches
        attr_match = d.get("attr_match")
        survey_m = am.get("survey_number_match")
        land_m = am.get("land_use_match")
        class_m = am.get("classification_match")
        if attr_match is None:
            mismatches = d.get("attribute_mismatch_count", 0)
            attr_match = 0.0 if mismatches > 0 else 1.0
            matches = [m for m in (survey_m, land_m, class_m) if m is not None]
            if matches:
                attr_match = float(np.mean([1.0 if m else 0.0 for m in matches]))
        attr_match = float(np.clip(attr_match, 0.0, 1.0))

        survey_val = 1.0 if survey_m is True else (0.0 if survey_m is False else (1.0 if (attr_match >= 0.5 and "attr_match" in d) else 0.0))
        land_val = 1.0 if land_m is True else (0.0 if land_m is False else (1.0 if (attr_match >= 0.5 and "attr_match" in d) else 0.0))
        class_val = 1.0 if class_m is True else (0.0 if class_m is False else (1.0 if (attr_match >= 0.5 and "attr_match" in d) else 0.0))

        return {
            "iou": iou,
            "area_ratio": area_ratio,
            "area_difference_m2": area_diff_m2,
            "area_delta": area_delta,
            "centroid_distance_m": centroid_d,
            "centroid_distance": centroid_d,
            "hausdorff_distance_m": hausdorff_d,
            "boundary_displacement_m": boundary_disp,
            "shape_similarity": shape_sim,
            "overlap_pct_of_cadastral": overlap_pct,
            "compactness_difference": compactness_diff,
            "perimeter_difference_m": perimeter_diff_m,
            "vertex_count_diff": abs(int(vertex_count_diff or 0)),
            "attr_match": attr_match,
            "survey_number_match": survey_val,
            "land_use_match": land_val,
            "classification_match": class_val,
        }

    def check_ood(self, raw_data: Any) -> Tuple[bool, str]:
        """
        Deterministic Out-Of-Distribution (OOD) check on physical and statistical boundaries.
        Returns (is_ood, reason).
        """
        if isinstance(raw_data, dict):
            # Check spatial metrics if nested
            sm = raw_data.get("spatial_metrics") if isinstance(raw_data.get("spatial_metrics"), dict) else {}
            iou = raw_data.get("iou") if "iou" in raw_data else raw_data.get("iou_score")
            if iou is None and "iou" in sm:
                iou = sm.get("iou")
            if iou is not None:
                try:
                    f_iou = float(iou)
                    if f_iou < 0.0 or f_iou > 1.0:
                        return True, f"IoU {f_iou:.3f} outside physical range [0.0, 1.0]"
                except (ValueError, TypeError):
                    pass

            area_delta = raw_data.get("area_delta")
            if area_delta is not None:
                try:
                    f_ad = float(area_delta)
                    if f_ad < 0.0 or f_ad > 1.0:
                        return True, f"area_delta {f_ad:.3f} outside normalized range [0.0, 1.0]"
                except (ValueError, TypeError):
                    pass

            attr_match = raw_data.get("attr_match")
            if attr_match is not None:
                try:
                    f_am = float(attr_match)
                    if f_am < 0.0 or f_am > 1.0:
                        return True, f"attr_match {f_am:.3f} outside range [0.0, 1.0]"
                except (ValueError, TypeError):
                    pass

            for key in ("area_difference", "area_difference_m2", "centroid_distance", "centroid_distance_m", "hausdorff_distance_m", "boundary_displacement_m"):
                val = raw_data.get(key)
                if val is None and key in sm:
                    val = sm.get(key)
                if val is not None:
                    try:
                        f_val = float(val)
                        if f_val < 0.0:
                            return True, f"{key} {f_val:.1f} cannot be negative"
                    except (ValueError, TypeError):
                        pass

        elif isinstance(raw_data, (list, tuple, np.ndarray)):
            vec = list(raw_data)
            if len(vec) == 3:
                iou, area_delta, attr_match = vec[0], vec[1], vec[2]
                if iou < 0.0 or iou > 1.0:
                    return True, f"IoU {iou:.3f} outside physical range [0.0, 1.0]"
                if area_delta < 0.0 or area_delta > 1.0:
                    return True, f"area_delta {area_delta:.3f} outside normalized range [0.0, 1.0]"
                if attr_match < 0.0 or attr_match > 1.0:
                    return True, f"attr_match {attr_match:.3f} outside range [0.0, 1.0]"
            elif len(vec) == len(FEATURE_ORDER):
                iou = vec[0]
                if iou is not None and (iou < 0.0 or iou > 1.0):
                    return True, f"IoU {iou:.3f} outside physical range [0.0, 1.0]"
                area_ratio = vec[1]
                if area_ratio is not None and (area_ratio < 0.0 or area_ratio > 1.0):
                    return True, f"area_ratio {area_ratio:.3f} outside range [0.0, 1.0]"
                area_diff = vec[2]
                if area_diff is not None and area_diff < 0.0:
                    return True, f"area_difference_m2 {area_diff:.1f} cannot be negative"
                cent_d = vec[3]
                if cent_d is not None and cent_d < 0.0:
                    return True, f"centroid_distance_m {cent_d:.1f} cannot be negative"

        return False, "In distribution"

    def extract_features(self, parcel_data: Dict) -> np.ndarray:
        """
        Extract feature vector matching the model's exact expected columns.
        Returns a 2D numpy array of shape (1, n_features).
        """
        feats_dict = self.extract_features_dict(parcel_data)
        vals = [feats_dict.get(name, 0.0) for name in self.feature_names]
        return np.array(vals, dtype=np.float64).reshape(1, -1)

    def predict_conflict(self, parcel_data: Any) -> MLPredictionResult:
        """
        Predict conflict level, confidence, probability, and explainable reasoning.
        Returns an MLPredictionResult (dict supporting legacy `has_conflict, confidence = ...`).
        """
        if not self.is_loaded or self.classifier is None:
            return MLPredictionResult({
                "model_status": "MODEL_UNAVAILABLE",
                "has_conflict": False,
                "conflict_level": -1,
                "conflict_label": "Unavailable",
                "confidence": 0.0,
                "probability": None,
                "probabilities": None,
                "reasoning": "ML model currently unavailable; falling back to deterministic GIS evidence.",
                "features_used": {},
                "model_version": self.model_version,
            })

        # OOD detection on raw input
        is_ood, ood_reason = self.check_ood(parcel_data)
        if is_ood:
            return MLPredictionResult({
                "model_status": "MODEL_OUT_OF_DISTRIBUTION",
                "has_conflict": False,
                "conflict_level": -1,
                "conflict_label": "Out of Distribution",
                "confidence": 0.0,
                "probability": None,
                "probabilities": None,
                "reasoning": f"MODEL_OUT_OF_DISTRIBUTION: {ood_reason}",
                "features_used": {},
                "model_version": self.model_version,
            })

        # Feature extraction
        feats_dict = self.extract_features_dict(parcel_data)

        # Build DataFrame with explicit feature names to ensure identical preprocessing
        x_df = pd.DataFrame(
            [[feats_dict.get(name, 0.0) for name in self.feature_names]],
            columns=self.feature_names,
        )

        if self.scaler is not None and hasattr(self.scaler, "transform"):
            x_in = self.scaler.transform(x_df)
        else:
            x_in = x_df

        # Predict class
        pred = int(self.classifier.predict(x_in)[0])
        has_conflict = (pred != 0)

        # Predict probability
        prob = None
        prob_dict = None
        confidence = 50.0
        if hasattr(self.classifier, "predict_proba"):
            try:
                classes = list(self.classifier.classes_)
                probas = self.classifier.predict_proba(x_in)[0]
                prob_dict = {f"class_{c}": float(round(p, 4)) for c, p in zip(classes, probas)}
                if pred in classes:
                    prob = float(probas[classes.index(pred)])
                    confidence = float(np.clip(round(prob * 100.0, 1), 0.0, 100.0))
            except Exception as e:
                logger.debug("Failed to compute predict_proba: %s", e)

        # Fallback to confidence regressor if present
        if self.confidence_model is not None and hasattr(self.confidence_model, "predict"):
            try:
                c_pred = float(self.confidence_model.predict(x_in)[0])
                confidence = float(np.clip(c_pred, 0.0, 100.0))
            except Exception:
                pass

        # Generate Explainable Reasoning (XAI)
        mapping = {0: "No Conflict", 1: "Minor Discrepancy", 2: "Critical Conflict"}
        label = mapping.get(pred, f"Class {pred}")

        iou_val = feats_dict.get("iou", 1.0)
        area_delta_val = feats_dict.get("area_delta", 0.0)
        attr_match_val = feats_dict.get("attr_match", 1.0)
        centroid_d_val = feats_dict.get("centroid_distance_m", 0.0)

        reasons = []
        if iou_val < 0.50:
            reasons.append(f"Low spatial overlap (IoU: {iou_val:.2f})")
        if area_delta_val > 0.25:
            reasons.append(f"Significant area discrepancy (Delta: {area_delta_val:.2f})")
        if attr_match_val < 0.60:
            reasons.append(f"Attribute mismatch (Match: {attr_match_val:.2f})")
        if centroid_d_val > 20.0:
            reasons.append(f"Centroid displacement ({centroid_d_val:.1f}m)")

        reasoning = f"{label} - " + (" | ".join(reasons) if reasons else "All metrics within normal bounds")

        return MLPredictionResult({
            "model_status": "OK",
            "has_conflict": has_conflict,
            "conflict_level": pred,
            "conflict_label": label,
            "confidence": confidence,
            "probability": prob,
            "probabilities": prob_dict,
            "reasoning": reasoning,
            "features_used": {k: float(round(feats_dict[k], 4)) for k in self.feature_names if k in feats_dict},
            "model_version": self.model_version,
        })

    def predict(self, feature_vector: List[float]) -> Dict[str, Any]:
        """
        Fusion interface compatible with `engine.pipeline.run_reconciliation`.
        Consumes the versioned canonical feature vector from `engine.ml_schema`.
        """
        res = self.predict_conflict(feature_vector)
        if res["model_status"] != "OK":
            return {
                "model_status": res["model_status"],
                "prediction": None,
                "probability": None,
                "model_version": self.model_version,
                "reasoning": res["reasoning"],
            }

        return {
            "model_status": "OK",
            "prediction": str(res["conflict_level"]),
            "probability": res["probability"],
            "conflict_label": res["conflict_label"],
            "model_version": self.model_version,
            "reasoning": res["reasoning"],
        }

    def get_metadata(self) -> Dict[str, Any]:
        """Expose honest metadata backed by verified held-out evaluation if present."""
        models_json_path = Path(__file__).resolve().parents[2] / "models" / "reconciliation_model.json"
        verified_eval = None
        if models_json_path.exists():
            try:
                import json
                with open(models_json_path, "r", encoding="utf-8") as f:
                    verified_eval = json.load(f)
            except Exception:
                verified_eval = None

        if verified_eval and verified_eval.get("test_metrics"):
            tm = verified_eval["test_metrics"]
            return {
                "model_status": "OK" if self.is_loaded else "MODEL_UNAVAILABLE",
                "load_status": self.load_status,
                "model_type": verified_eval.get("model_type", type(self.classifier).__name__ if self.classifier else None),
                "model_version": verified_eval.get("model_version", self.model_version),
                "model_hash_sha256": verified_eval.get("model_hash_sha256"),
                "dataset_hash_sha256": verified_eval.get("dataset_hash_sha256"),
                "feature_schema_version": verified_eval.get("feature_schema_version", self.feature_schema_version),
                "feature_names": verified_eval.get("feature_order", self.feature_names),
                "feature_count": len(verified_eval.get("feature_order", self.feature_names)),
                "classes": verified_eval.get("classes", [int(c) for c in self.classifier.classes_] if hasattr(self.classifier, "classes_") else []),
                "class_names": verified_eval.get("class_names", ["No Conflict (MATCH)", "Minor Conflict", "Critical Conflict"]),
                "accuracy": tm.get("accuracy"),
                "accuracy_status": f"VERIFIED: {tm.get('accuracy', 0.0) * 100:.2f}% on held-out test set ({verified_eval.get('test_samples')} samples).",
                "balanced_accuracy": tm.get("balanced_accuracy"),
                "f1_macro": tm.get("f1_macro"),
                "precision_macro": tm.get("precision_macro"),
                "recall_macro": tm.get("recall_macro"),
                "confusion_matrix": tm.get("confusion_matrix"),
                "cross_validation": verified_eval.get("cross_validation"),
                "provenance": verified_eval.get("provenance"),
                "is_calibrated": True,
            }

        return {
            "model_status": "OK" if self.is_loaded else "MODEL_UNAVAILABLE",
            "load_status": self.load_status,
            "model_type": type(self.classifier).__name__ if self.classifier else None,
            "model_path": str(self.model_path),
            "model_version": self.model_version,
            "feature_schema_version": self.feature_schema_version,
            "feature_names": self.feature_names,
            "feature_count": len(self.feature_names),
            "classes": [int(c) for c in self.classifier.classes_] if hasattr(self.classifier, "classes_") and self.classifier.classes_ is not None else [],
            "accuracy": None,
            "accuracy_status": "UNMEASURED: Genuine human-verified labels not available; test accuracy cannot be measured without verified ground truth.",
            "is_calibrated": False,
        }

    def train(self, training_data: List[Dict], labels: List[int]):
        """
        Train conflict detection model on verified multi-class data.
        Refuses to train on synthetic demo fixtures (spec §2, §10).
        """
        # Guardrail: check for synthetic fixture markers
        for rec in training_data:
            text = str(rec).lower()
            if any(marker in text for marker in ("sample", "mock", "fixture", "synthetic")):
                raise ValueError("Refusing to train: training data contains synthetic fixture markers (spec §2/§10).")

        if len(set(labels)) < 2:
            raise ValueError("Training data must contain at least 2 distinct classes.")

        if len(training_data) < 10:
            raise ValueError("Insufficient training samples (minimum 10 required).")

        x_list = [self.extract_features(d)[0] for d in training_data]
        x_mat = np.array(x_list)
        y_vec = np.array(labels)

        x_train, x_test, y_train, y_test = train_test_split(
            x_mat, y_vec, test_size=0.2, random_state=42, stratify=y_vec
        )

        scaler = StandardScaler()
        x_train_scaled = scaler.fit_transform(x_train)
        x_test_scaled = scaler.transform(x_test)

        clf = RandomForestClassifier(n_estimators=100, random_state=42)
        clf.fit(x_train_scaled, y_train)

        self.classifier = clf
        self.scaler = scaler
        self.is_loaded = True
        self.load_status = "OK"
        self.save_model()

    def save_model(self):
        """Save trained model to disk."""
        self.model_path.parent.mkdir(parents=True, exist_ok=True)
        with open(self.model_path, "wb") as f:
            pickle.dump({
                "classifier": self.classifier,
                "confidence_model": self.confidence_model,
                "scaler": self.scaler,
                "feature_names": self.feature_names,
                "feature_schema_version": self.feature_schema_version,
                "model_version": self.model_version,
            }, f)
        logger.info("Model saved to %s", self.model_path)


class TopologyValidator:
    """Validate geospatial topology."""

    @staticmethod
    def validate_topology(geometry) -> Dict[str, bool]:
        results = {
            "is_valid": geometry.is_valid,
            "is_simple": geometry.is_simple,
            "has_self_intersection": not geometry.is_simple,
            "meets_min_area": geometry.area > 1.0,
            "is_closed": geometry.boundary.is_closed if hasattr(geometry, "boundary") else True,
        }
        return results

    @staticmethod
    def check_overlap(geom1, geom2, threshold: float = 0.01) -> bool:
        if not geom1.intersects(geom2):
            return False
        overlap = geom1.intersection(geom2)
        return overlap.area > threshold

    @staticmethod
    def check_gap(geom1, geom2, threshold: float = 1.0) -> bool:
        return geom1.distance(geom2) > threshold


class RecordLinkageEngine:
    """Link records across multiple data sources."""

    def __init__(self):
        self.linkage_rules = []

    def add_linkage_rule(self, field: str, match_type: str = "exact", threshold: float = 0.9):
        self.linkage_rules.append({
            "field": field,
            "match_type": match_type,
            "threshold": threshold,
        })

    def link_records(self, source1: List[Dict], source2: List[Dict]) -> List[Tuple[int, int, float]]:
        matches = []
        for i, rec1 in enumerate(source1):
            for j, rec2 in enumerate(source2):
                confidence = self._calculate_match_score(rec1, rec2)
                if confidence > 0.8:
                    matches.append((i, j, confidence))
        return matches

    def _calculate_match_score(self, rec1: Dict, rec2: Dict) -> float:
        scores = []
        for rule in self.linkage_rules:
            field = rule["field"]
            if field in rec1 and field in rec2:
                score = 1.0 if rec1[field] == rec2[field] else (0.5 if rule["match_type"] != "exact" else 0.0)
                scores.append(score)
        return float(np.mean(scores)) if scores else 0.0


# Initialize global instances
_MODEL_PATH = Path(__file__).resolve().parent.parent / "models" / "conflict_detector.pkl"
conflict_detector = ConflictDetectionModel(model_path=_MODEL_PATH)
topology_validator = TopologyValidator()
record_linker = RecordLinkageEngine()
