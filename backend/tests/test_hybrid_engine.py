"""
backend/tests/test_hybrid_engine.py
===================================
Spec §26 tests for the hybrid engine layers: deterministic metrics,
geometry normalisation, candidate classification, evidence fusion,
ML schema/registry honesty, and the new API endpoints.
"""

from __future__ import annotations

import math

import pytest
from shapely.geometry import Polygon

from engine.candidates import MatchingThresholds, classify_status
from engine.metrics import compute_pair_metrics
from engine.fusion import evidence_quality, fuse, geometric_agreement
from engine.ml_schema import FEATURE_ORDER, FEATURE_SCHEMA_VERSION, features_from_pair_metrics


def _sq(x=0.0, y=0.0, s=100.0):
    return Polygon([(x, y), (x + s, y), (x + s, y + s), (x, y + s), (x, y)])


class TestDeterministicMetrics:
    def test_iou_identical_polygons_is_one(self):
        m = compute_pair_metrics(_sq(), _sq())
        assert m["spatial_metrics"]["iou"] == pytest.approx(1.0)

    def test_iou_disjoint_is_zero(self):
        m = compute_pair_metrics(_sq(0, 0), _sq(1000, 1000))
        assert m["spatial_metrics"]["iou"] == pytest.approx(0.0)

    def test_area_ratio_formula(self):
        a, b = _sq(s=100.0), _sq(s=50.0)  # 10000 vs 2500 m²
        m = compute_pair_metrics(a, b)
        assert m["spatial_metrics"]["area_ratio"] == pytest.approx(0.25)
        assert m["spatial_metrics"]["area_difference_m2"] == pytest.approx(7500.0)

    def test_centroid_distance_is_metric(self):
        m = compute_pair_metrics(_sq(0, 0), _sq(30, 40))
        assert m["spatial_metrics"]["centroid_distance_m"] == pytest.approx(50.0)

    def test_determinism_bit_identical(self):
        a, b = _sq(10, 10, 80), _sq(12, 9, 85)
        r1 = compute_pair_metrics(a, b)
        r2 = compute_pair_metrics(a, b)
        assert r1 == r2

    def test_missing_attributes_yield_none_not_false(self):
        m = compute_pair_metrics(_sq(), _sq(), attrs_a={}, attrs_b={})
        assert m["attribute_metrics"]["survey_number_match"] is None

    def test_attribute_agreement(self):
        m = compute_pair_metrics(
            _sq(), _sq(),
            attrs_a={"survey_number": "123", "land_use": "Agri"},
            attrs_b={"survey_number": "123", "land_use": "Residential"},
        )
        assert m["attribute_metrics"]["survey_number_match"] is True
        assert m["attribute_metrics"]["land_use_match"] is False

    def test_imagery_absent_is_explicit(self):
        m = compute_pair_metrics(_sq(), _sq())
        assert m["imagery"]["available"] is False
        assert m["imagery"]["acquisition_date"] is None


class TestGeometryNormalization:
    def test_repair_bowtie_polygon(self):
        import geopandas as gpd
        from engine.geometry import normalize_geometries

        # A self-intersecting "bow tie" polygon.
        bowtie = Polygon([(0, 0), (2, 2), (2, 0), (0, 2), (0, 0)])
        gdf = gpd.GeoDataFrame(
            {"parcel_id": ["A"]}, geometry=[bowtie], crs="EPSG:3857"
        )
        cleaned, report = normalize_geometries(gdf, source_name="test")
        assert report["repaired"] == 1
        assert len(cleaned) == 1
        assert cleaned.geometry.iloc[0].is_valid

    def test_empty_geometry_dropped(self):
        import geopandas as gpd
        from engine.geometry import normalize_geometries

        gdf = gpd.GeoDataFrame(
            {"parcel_id": ["A", "B"]},
            geometry=[_sq(), Polygon()],  # second empty
            crs="EPSG:3857",
        )
        cleaned, report = normalize_geometries(gdf, source_name="test")
        assert report["dropped_empty"] == 1
        assert len(cleaned) == 1

    def test_impossible_coordinates_rejected(self):
        import geopandas as gpd
        from engine.geometry import normalize_geometries

        # Bounds far outside the EPSG:3857 domain (datum/unit error).
        huge = Polygon([(1e8, 1e8), (1.1e8, 1e8), (1.1e8, 1.1e8), (1e8, 1.1e8), (1e8, 1e8)])
        gdf = gpd.GeoDataFrame(
            {"parcel_id": ["A", "B"]}, geometry=[_sq(), huge], crs="EPSG:3857"
        )
        cleaned, report = normalize_geometries(gdf, source_name="test")
        assert report["dropped_impossible_coords"] == 1
        assert len(cleaned) == 1


class TestCandidateStatus:
    TH = MatchingThresholds()

    def test_match(self):
        assert classify_status(0.95, 99.0, 2.0, False, self.TH) == "MATCH"

    def test_match_with_attribute_conflict_requires_review(self):
        assert classify_status(0.95, 99.0, 2.0, True, self.TH) == "REVIEW_REQUIRED"

    def test_minor_discrepancy(self):
        assert classify_status(0.55, 80.0, 10.0, False, self.TH) == "MINOR_DISCREPANCY"

    def test_major_discrepancy(self):
        assert classify_status(0.10, 40.0, 30.0, False, self.TH) == "MAJOR_DISCREPANCY"

    def test_weak_overlap_requires_review(self):
        assert classify_status(0.05, 3.0, 500.0, False, self.TH) == "REVIEW_REQUIRED"


class TestFusion:
    def test_geometric_agreement_formula(self):
        # 0.55*1.0 + 0.30*1.0 + 0.15*(1 - 15/150) = 0.985
        assert geometric_agreement(1.0, 1.0, 15.0) == pytest.approx(0.985)

    def test_score_is_not_probability_of_correctness(self):
        fused = fuse(
            parcel_id="X",
            candidate_status="MATCH",
            spatial_metrics={"iou": 1.0, "area_ratio": 1.0, "centroid_distance_m": 0.0},
        )
        assert fused["reconciliation_score"] == 100
        assert "NOT a calibrated accuracy" in fused["fusion_method"]

    def test_unmatched_always_review(self):
        fused = fuse(
            parcel_id="X",
            candidate_status="UNMATCHED",
            spatial_metrics={"iou": None},
        )
        assert fused["review_required"] is True
        assert fused["match_status"] == "UNMATCHED"

    def test_ml_disagreement_promotes_review_only(self):
        fused = fuse(
            parcel_id="X",
            candidate_status="MATCH",
            spatial_metrics={"iou": 0.95, "area_ratio": 0.99, "centroid_distance_m": 2.0},
            model={"model_status": "OK", "prediction": "MAJOR_DISCREPANCY", "probability": 0.9},
        )
        assert fused["review_required"] is True

    def test_ml_cannot_upgrade_review_to_match(self):
        fused = fuse(
            parcel_id="X",
            candidate_status="REVIEW_REQUIRED",
            spatial_metrics={"iou": 0.05, "area_ratio": 0.2, "centroid_distance_m": 400.0},
            model={"model_status": "OK", "prediction": "MATCH", "probability": 0.99},
        )
        assert fused["match_status"] == "REVIEW_REQUIRED"

    def test_model_unavailable_honest(self):
        fused = fuse(
            parcel_id="X",
            candidate_status="MATCH",
            spatial_metrics={"iou": 0.95, "area_ratio": 1.0, "centroid_distance_m": 1.0},
        )
        assert fused["model_status"] == "MODEL_UNAVAILABLE"

    def test_evidence_quality_rubric(self):
        assert evidence_quality(0.9, {"survey_number_match": True}, None) == "HIGH"
        assert evidence_quality(0.5, {}, None) == "LOW"
        assert evidence_quality(None, None, None) == "INSUFFICIENT"


class TestMLSchema:
    def test_feature_vector_complete(self):
        m = compute_pair_metrics(
            _sq(), _sq(s=90.0),
            attrs_a={"survey_number": "1", "land_use": "A", "classification": "B"},
            attrs_b={"survey_number": "1", "land_use": "A", "classification": "B"},
        )
        feats = features_from_pair_metrics(m)
        assert set(feats.keys()) == set(FEATURE_ORDER)
        assert all(v is not None for v in feats.values())

    def test_schema_version_present(self):
        assert FEATURE_SCHEMA_VERSION


class TestModelRegistry:
    def test_no_artifact_is_honest(self, tmp_path, monkeypatch):
        import backend.services.model_info as mi

        monkeypatch.setattr(mi, "ARTIFACT_PATH", tmp_path / "missing.json")
        monkeypatch.setattr(mi, "METADATA_PATH", tmp_path / "missing_meta.json")
        registry = mi.ModelRegistry()
        assert not registry.available
        info = registry.info()
        assert info["model_status"] == "MODEL_UNAVAILABLE"
        assert "reason" in info

    def test_single_class_artifact_rejected(self, tmp_path, monkeypatch):
        import backend.services.model_info as mi

        artifact = {
            "feature_schema_version": FEATURE_SCHEMA_VERSION,
            "model_type": "rf",
            "training_class_distribution": {"MATCH": 10},
            "test_metrics": {"accuracy": 1.0, "f1_macro": 1.0},
        }
        path = tmp_path / "a.json"
        path.write_text(json.dumps(artifact))
        monkeypatch.setattr(mi, "ARTIFACT_PATH", path)
        registry = mi.ModelRegistry()
        assert not registry.available
        assert "single class" in registry.reason


import json  # noqa: E402  (kept at bottom to not disturb the imports above)
