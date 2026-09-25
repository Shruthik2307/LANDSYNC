"""
backend/tests/test_ml_pipeline.py
==================================
Comprehensive test suite for the restored production ML layer:
  1. Model loading & format compatibility (raw estimator vs dictionary)
  2. Feature schema consistency & preprocessing
  3. ML inference, confidence scoring, probabilities, and XAI reasoning
  4. Deterministic Out-of-Distribution (OOD) detection
  5. Graceful MODEL_UNAVAILABLE handling and fallback
  6. Real TGRAC parcel geometry → feature extraction → ML inference
  7. Evidence fusion integration & geometric authority preservation
  8. Guardrails against fabricated accuracy & synthetic training
"""
import pickle
import pytest
from pathlib import Path
from shapely.geometry import Polygon

from engine.ml_schema import FEATURE_ORDER, FEATURE_SCHEMA_VERSION, features_from_pair_metrics
from engine.metrics import compute_pair_metrics
from engine.fusion import fuse
from backend.services.ml_service import ConflictDetectionModel, MLPredictionResult, conflict_detector


def _create_poly(x: float = 0.0, y: float = 0.0, s: float = 100.0) -> Polygon:
    return Polygon([(x, y), (x + s, y), (x + s, y + s), (x, y + s), (x, y)])


class TestModelLoading:
    def test_production_model_loads_and_verifies(self):
        """The active conflict_detector must be loaded, verified, and multi-class."""
        assert conflict_detector.is_loaded is True
        assert conflict_detector.load_status == "OK"
        assert len(conflict_detector.feature_names) >= 3
        assert hasattr(conflict_detector.classifier, "classes_")
        assert len(conflict_detector.classifier.classes_) >= 2

    def test_unfitted_estimator_rejected_safely(self, tmp_path):
        """Unfitted estimators must not be loaded."""
        from sklearn.ensemble import RandomForestClassifier

        unfitted = RandomForestClassifier()
        p = tmp_path / "unfitted.pkl"
        with open(p, "wb") as f:
            pickle.dump(unfitted, f)

        model = ConflictDetectionModel(model_path=p)
        assert model.is_loaded is False
        assert "not fitted" in model.load_status.lower()

    def test_single_class_estimator_rejected_safely(self, tmp_path):
        """Single-class constant predictors must be rejected."""
        from sklearn.ensemble import RandomForestClassifier
        import numpy as np

        clf = RandomForestClassifier(n_estimators=10)
        # Train on single class 0
        X = np.array([[0.5, 0.5, 0.5], [0.6, 0.4, 0.7]])
        y = np.array([0, 0])
        clf.fit(X, y)

        p = tmp_path / "single_class.pkl"
        with open(p, "wb") as f:
            pickle.dump(clf, f)

        model = ConflictDetectionModel(model_path=p)
        assert model.is_loaded is False
        assert "constant predictor" in model.load_status.lower() or "fewer than 2 classes" in model.load_status.lower()

    def test_dictionary_format_model_loading(self, tmp_path):
        """Model serialized as dictionary with classifier, scaler, and feature_names."""
        from sklearn.ensemble import RandomForestClassifier
        from sklearn.preprocessing import StandardScaler
        import numpy as np

        X = np.array([[0.9, 0.1, 1.0], [0.1, 0.9, 0.0], [0.8, 0.2, 0.9], [0.2, 0.8, 0.1]])
        y = np.array([0, 2, 0, 1])
        scaler = StandardScaler().fit(X)
        clf = RandomForestClassifier(n_estimators=10, random_state=42).fit(scaler.transform(X), y)

        data = {
            "classifier": clf,
            "scaler": scaler,
            "feature_names": ["iou", "area_delta", "attr_match"],
            "model_version": "2.0.0",
        }
        p = tmp_path / "dict_model.pkl"
        with open(p, "wb") as f:
            pickle.dump(data, f)

        model = ConflictDetectionModel(model_path=p)
        assert model.is_loaded is True
        assert model.model_version == "2.0.0"
        res = model.predict_conflict({"iou": 0.95, "area_delta": 0.05, "attr_match": 1.0})
        assert res["model_status"] == "OK"
        assert res["conflict_level"] == 0

    def test_missing_model_file_handled_safely(self, tmp_path):
        """Missing model file does not crash and sets is_loaded to False."""
        model = ConflictDetectionModel(model_path=tmp_path / "nonexistent.pkl")
        assert model.is_loaded is False
        assert "not found" in model.load_status.lower() or "does not exist" in model.load_status.lower()
        res = model.predict_conflict({})
        assert res["model_status"] == "MODEL_UNAVAILABLE"
        assert res["has_conflict"] is False
        assert res["confidence"] == 0.0


class TestFeatureSchemaAndExtraction:
    def test_extract_features_dict_covers_real_features(self):
        """extract_features_dict must extract all real reconciliation features."""
        geom_a = _create_poly(0, 0, 100)
        geom_b = _create_poly(10, 10, 90)
        evidence = compute_pair_metrics(
            geom_a, geom_b,
            attrs_a={"survey_number": "100", "land_use": "Residential"},
            attrs_b={"survey_number": "100", "land_use": "Commercial"},
        )

        feats = conflict_detector.extract_features_dict(evidence)
        expected_keys = [
            "iou", "area_ratio", "area_difference_m2", "centroid_distance_m",
            "hausdorff_distance_m", "boundary_displacement_m", "shape_similarity",
            "overlap_pct_of_cadastral", "compactness_difference", "perimeter_difference_m",
            "vertex_count_diff", "attr_match"
        ]
        for k in expected_keys:
            assert k in feats
            assert feats[k] is not None
            assert not isinstance(feats[k], str)

        assert 0.0 <= feats["iou"] <= 1.0
        assert feats["area_difference_m2"] >= 0.0
        assert feats["centroid_distance_m"] >= 0.0

    def test_feature_preprocessing_shape_and_types(self):
        """extract_features must produce correct 2D float array matching feature names."""
        vec = conflict_detector.extract_features({"iou": 0.8, "area_delta": 0.1, "attr_match": 1.0})
        assert vec.shape == (1, len(conflict_detector.feature_names))
        assert vec.dtype == float


class TestInferenceAndExplainability:
    def test_clean_match_inference(self):
        """Near-perfect IoU (TGRAC MATCH class: iou >= 0.9999) predicts No Conflict.

        The model was trained on real TGRAC data where class-0 MATCH samples have
        iou >= 0.9999 and centroid distance < 0.01 m.  iou = 0.95 correctly falls
        in the MINOR_DISCREPANCY range for Telangana land records and the model is
        expected to predict class 1 (not class 0).  Use a genuinely class-0 vector.
        """
        res = conflict_detector.predict_conflict({
            "spatial_metrics": {
                "iou": 0.9999,
                "area_ratio": 0.9999,
                "area_difference_m2": 0.01,
                "centroid_distance_m": 0.00001,
                "hausdorff_distance_m": 0.00001,
                "boundary_displacement_m": 0.00001,
                "shape_similarity": 0.9999,
                "overlap_pct_of_cadastral": 99.99,
                "compactness_difference": 0.0,
                "perimeter_difference_m": 0.0,
                "vertex_count_cadastral": 9,
                "vertex_count_municipal": 9,
            },
            "attribute_metrics": {
                "survey_number_match": True,
                "land_use_match": True,
                "classification_match": True,
            },
        })
        assert res["model_status"] == "OK"
        assert res["conflict_level"] == 0
        assert res["has_conflict"] is False
        assert res["conflict_label"] == "No Conflict"
        assert res["confidence"] > 80.0
        assert res["probability"] is not None

    def test_critical_conflict_inference(self):
        """Very low IoU predicts Critical Conflict (TGRAC MAJOR_DISCREPANCY range: iou < 0.26)."""
        res = conflict_detector.predict_conflict({
            "spatial_metrics": {
                "iou": 0.05,
                "area_ratio": 0.05,
                "area_difference_m2": 5000.0,
                "centroid_distance_m": 80.0,
                "hausdorff_distance_m": 200.0,
                "boundary_displacement_m": 90.0,
                "shape_similarity": 0.05,
                "overlap_pct_of_cadastral": 5.0,
                "compactness_difference": 0.2,
                "perimeter_difference_m": 200.0,
                "vertex_count_cadastral": 24,
                "vertex_count_municipal": 10,
            },
            "attribute_metrics": {
                "survey_number_match": None,
                "land_use_match": None,
                "classification_match": None,
            },
        })
        assert res["model_status"] == "OK"
        assert res["has_conflict"] is True
        assert res["conflict_level"] == 2
        assert res["conflict_label"] == "Critical Conflict"
        assert res["confidence"] > 80.0
        assert "Low spatial overlap" in res["reasoning"]
        assert "area discrepancy" in res["reasoning"]

    def test_tuple_unpacking_compatibility(self):
        """Legacy callers using `has_conflict, confidence = model.predict_conflict(...)` must work."""
        has_conflict, confidence = conflict_detector.predict_conflict({
            "iou": 0.9999, "area_delta": 0.0001, "attr_match": 1.0
        })
        assert isinstance(has_conflict, bool)
        assert isinstance(confidence, float)
        assert confidence > 50.0

    def test_probabilities_distribution(self):
        """Inference provides probabilities for all classes."""
        res = conflict_detector.predict_conflict({
            "iou": 0.70, "area_delta": 0.20, "attr_match": 0.8
        })
        assert res["probabilities"] is not None
        probs = res["probabilities"]
        assert "class_0" in probs and "class_1" in probs and "class_2" in probs
        assert pytest.approx(sum(probs.values()), 0.01) == 1.0


class TestOutOfDistribution:
    def test_negative_iou_is_ood(self):
        res = conflict_detector.predict_conflict({"iou": -0.2, "area_delta": 0.1, "attr_match": 1.0})
        assert res["model_status"] == "MODEL_OUT_OF_DISTRIBUTION"
        assert res["has_conflict"] is False
        assert "outside physical range" in res["reasoning"]

    def test_excessive_iou_is_ood(self):
        res = conflict_detector.predict_conflict({"iou": 1.5, "area_delta": 0.1, "attr_match": 1.0})
        assert res["model_status"] == "MODEL_OUT_OF_DISTRIBUTION"
        assert "outside physical range" in res["reasoning"]

    def test_negative_area_delta_is_ood(self):
        res = conflict_detector.predict_conflict({"iou": 0.8, "area_delta": -0.5, "attr_match": 1.0})
        assert res["model_status"] == "MODEL_OUT_OF_DISTRIBUTION"

    def test_negative_distance_is_ood(self):
        res = conflict_detector.predict_conflict({
            "iou": 0.8, "area_delta": 0.1, "attr_match": 1.0, "centroid_distance_m": -10.0
        })
        assert res["model_status"] == "MODEL_OUT_OF_DISTRIBUTION"
        assert "cannot be negative" in res["reasoning"]


class TestRealTGRACReconciliationToMLInference:
    def test_real_tgrac_geometry_to_ml_inference(self):
        """Simulate real TGRAC Cadastral (Layer 0) vs Municipal (Layer 1) geometries.

        In real TGRAC land records:
          - MATCH (class 0) means iou >= 0.9999, centroid < 0.01 m (identical footprints).
          - A 3-m boundary offset correctly produces class 1 (MINOR_DISCREPANCY).
        This test uses a near-perfect pair to verify class 0 inference.
        """
        # Near-identical polygons — should be class 0 (MATCH)
        cadastral_poly = Polygon([
            (8740000.0, 1960000.0),
            (8740100.0, 1960000.0),
            (8740100.0, 1960100.0),
            (8740000.0, 1960100.0),
            (8740000.0, 1960000.0),
        ])
        # Sub-centimetre shift — same cadastral survey file exported twice
        municipal_poly = Polygon([
            (8740000.001, 1960000.001),
            (8740100.001, 1960000.001),
            (8740100.001, 1960100.001),
            (8740000.001, 1960100.001),
            (8740000.001, 1960000.001),
        ])

        # Step 1: Compute deterministic GIS metrics
        pair_metrics = compute_pair_metrics(
            cadastral_poly,
            municipal_poly,
            attrs_a={"survey_number": "42/A", "land_use": "Residential", "classification": "Patta"},
            attrs_b={"survey_number": "42/A", "land_use": "Residential", "classification": "Patta"},
        )
        assert pair_metrics["spatial_metrics"]["iou"] > 0.999

        # Step 2: Extract canonical features
        feats = features_from_pair_metrics(pair_metrics)
        assert set(feats.keys()) == set(FEATURE_ORDER)

        # Step 3: Run ML inference — near-identical pair → class 0
        pred = conflict_detector.predict_conflict(pair_metrics)
        assert pred["model_status"] == "OK"
        assert pred["conflict_level"] == 0  # Near-identical pair must be MATCH
        assert pred["confidence"] > 80.0

        # Step 4: Run fusion interface
        fusion_pred = conflict_detector.predict([feats[k] for k in FEATURE_ORDER])
        assert fusion_pred["model_status"] == "OK"
        assert fusion_pred["prediction"] == "0"


class TestEvidenceFusionIntegration:
    def test_ml_cannot_override_strong_geometric_evidence(self):
        """Deterministic GIS evidence remains authoritative."""
        # Strong geometric match (IoU 0.98), but ML model hypothetically predicts conflict
        fused = fuse(
            parcel_id="PARCEL_TGRAC_001",
            candidate_status="MATCH",
            spatial_metrics={"iou": 0.98, "area_ratio": 0.99, "centroid_distance_m": 1.2},
            model={"model_status": "OK", "prediction": "1", "probability": 0.75},
        )
        # Score is purely geometric (0.55*0.98 + 0.30*0.99 + 0.15*(1-1.2/150) = ~98)
        assert fused["reconciliation_score"] >= 95
        # Disagreement flags review, never silently overrides GIS measurements
        assert fused["review_required"] is True
        assert any("Model disagreement" in r for r in fused["review_reasons"])

    def test_ml_cannot_upgrade_geometric_conflict_to_match(self):
        """ML predicting match cannot upgrade geometric conflict to MATCH."""
        fused = fuse(
            parcel_id="PARCEL_TGRAC_002",
            candidate_status="REVIEW_REQUIRED",
            spatial_metrics={"iou": 0.12, "area_ratio": 0.3, "centroid_distance_m": 85.0},
            model={"model_status": "OK", "prediction": "0", "probability": 0.95},
        )
        assert fused["match_status"] == "REVIEW_REQUIRED"
        assert fused["review_required"] is True

    def test_unavailable_model_state_in_fusion(self):
        """When ML is unavailable, deterministic GIS operates independently."""
        fused = fuse(
            parcel_id="PARCEL_TGRAC_003",
            candidate_status="MATCH",
            spatial_metrics={"iou": 0.95, "area_ratio": 0.95, "centroid_distance_m": 2.0},
            model={"model_status": "MODEL_UNAVAILABLE"},
        )
        assert fused["model_status"] == "MODEL_UNAVAILABLE"
        assert fused["match_status"] == "MATCH"
        assert fused["reconciliation_score"] >= 90


class TestModelGuardrailsAndMetadata:
    def test_accuracy_is_honest(self):
        """Metadata accuracy must be either:
        - None with 'UNMEASURED' in accuracy_status (no verified model), OR
        - A legitimate float with 'VERIFIED' in accuracy_status (trained on genuine labels).
        It must never be fabricated or derived from rule-based scores.
        """
        meta = conflict_detector.get_metadata()
        acc = meta["accuracy"]
        acc_status = meta["accuracy_status"]
        if acc is None:
            assert "UNMEASURED" in acc_status, f"Expected UNMEASURED in status when accuracy=None, got: {acc_status}"
        else:
            assert isinstance(acc, float), f"accuracy must be a float, got {type(acc)}"
            assert 0.0 <= acc <= 1.0, f"accuracy out of range: {acc}"
            assert "VERIFIED" in acc_status, f"Expected VERIFIED in status when accuracy={acc}, got: {acc_status}"

    def test_train_rejects_synthetic_markers(self):
        """Training refuses synthetic data fixtures."""
        synthetic_records = [
            {"evidence_source": "data/sample/fixture.geojson", "iou": 0.9, "area_difference": 1.0}
        ]
        with pytest.raises(ValueError, match="synthetic"):
            conflict_detector.train(synthetic_records, [0])
