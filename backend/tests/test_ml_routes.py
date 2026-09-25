"""
backend/tests/test_ml_routes.py
================================
Tests for ML API endpoints: /api/ml/status, /api/ml/predict, /api/ml/predict-metrics
"""
import pytest
from fastapi.testclient import TestClient
from backend.main import app
from backend.services.ml_service import conflict_detector


@pytest.fixture
def client():
    return TestClient(app)


def test_ml_status_endpoint(client):
    """GET /api/ml/status returns production metadata with honest accuracy status.

    accuracy is None when no verified model exists (UNMEASURED).
    accuracy is a legitimate float when trained on genuine human-reviewed labels (VERIFIED).
    It must never be fabricated from rule-based scores.
    """
    res = client.get("/api/ml/status")
    assert res.status_code == 200
    data = res.json()
    assert data["model_status"] in ("OK", "MODEL_UNAVAILABLE")
    assert "feature_names" in data
    assert "accuracy_status" in data
    acc = data["accuracy"]
    acc_status = data["accuracy_status"]
    if acc is None:
        assert "UNMEASURED" in acc_status
    else:
        assert isinstance(acc, float) and 0.0 <= acc <= 1.0
        assert "VERIFIED" in acc_status


def test_ml_predict_clean_match(client):
    """POST /api/ml/predict with near-perfect metrics predicts No Conflict.

    Uses TGRAC-calibrated class-0 vector: iou >= 0.9999, centroid < 0.001 m.
    In real TGRAC data, iou=0.95 maps to MINOR_DISCREPANCY, not MATCH.
    """
    res = client.post("/api/ml/predict", json={
        "iou": 0.9999,
        "area_delta": 0.0001,
        "attr_match": 1.0,
    })
    assert res.status_code == 200
    data = res.json()
    assert data["conflict_level"] == 0
    assert data["conflict_label"] == "No Conflict"
    assert data["confidence"] > 80.0
    assert "probability" in data
    assert "reasoning" in data


def test_ml_predict_critical_conflict(client):
    """POST /api/ml/predict detects critical conflict on TGRAC-range MAJOR_DISCREPANCY vectors."""
    res = client.post("/api/ml/predict", json={
        "iou": 0.05,
        "area_delta": 0.95,
        "attr_match": 0.0,
    })
    assert res.status_code == 200
    data = res.json()
    assert data["conflict_level"] == 2
    assert data["conflict_label"] == "Critical Conflict"
    assert "Low spatial overlap" in data["reasoning"]


def test_ml_predict_out_of_distribution(client):
    """POST /api/ml/predict returns HTTP 422 on physical OOD metrics."""
    res = client.post("/api/ml/predict", json={
        "iou": -0.5,
        "area_delta": 0.02,
        "attr_match": 1.0,
    })
    assert res.status_code == 422
    assert "out of distribution" in res.json()["detail"].lower()


def test_ml_predict_metrics_endpoint(client):
    """POST /api/ml/predict-metrics accepts full GIS pair metrics.

    Uses near-perfect spatial metrics (iou=0.9999) and all attribute matches True.
    In real TGRAC land records this is a class-0 MATCH.
    """
    res = client.post("/api/ml/predict-metrics", json={
        "spatial_metrics": {
            "iou": 0.9999,
            "area_ratio": 0.9999,
            "area_difference_m2": 0.001,
            "centroid_distance_m": 0.00001,
            "hausdorff_distance_m": 0.00001,
            "boundary_displacement_m": 0.00001,
            "shape_similarity": 0.9999,
            "overlap_pct_of_cadastral": 99.99,
            "compactness_difference": 0.0,
            "perimeter_difference_m": 0.0,
        },
        "attribute_metrics": {
            "survey_number_match": True,
            "land_use_match": True,
            "classification_match": True,
        }
    })
    assert res.status_code == 200
    data = res.json()
    assert data["model_status"] == "OK"
    assert data["conflict_level"] == 0
    assert data["confidence"] > 80.0
