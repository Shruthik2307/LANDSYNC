"""
backend/tests/test_tgrac.py
===========================
Integration tests for verified real TGRAC ArcGIS REST service integration.
"""

import pytest
from fastapi.testclient import TestClient

from config import settings
from main import app
from services import landsync_service


@pytest.fixture()
def client():
    return TestClient(app)


class TestTGRACIntegration:
    def test_tgrac_status_endpoint(self, client):
        """GET /api/tgrac/status must verify live official TGRAC service."""
        resp = client.get("/api/tgrac/status")
        assert resp.status_code == 200
        data = resp.json()
        assert data["provider"] == "Telangana State Remote Sensing Applications Centre (TGRAC)"
        assert "Bhunaksha_Cadastral" in data["services"]
        assert "Bhunaksha_query" in data["services"]
        assert data["overall_status"] == "OK"

    def test_tgrac_layers_endpoint(self, client):
        """GET /api/tgrac/layers lists queryable official layers."""
        resp = client.get("/api/tgrac/layers")
        assert resp.status_code == 200
        data = resp.json()
        assert "Bhunaksha_Cadastral" in data
        assert len(data["Bhunaksha_Cadastral"]) > 0
        layer_names = [l["name"] for l in data["Bhunaksha_Cadastral"]]
        assert "Cadastral 2.5m" in layer_names

    def test_tgrac_query_vector_features(self, client):
        """POST /api/tgrac/query returns real GeoJSON vector features with provenance."""
        payload = {
            "service": "Bhunaksha_Cadastral",
            "layer_id": 0,
            "bbox": [78.06, 17.60, 78.08, 17.62],
            "max_records": 10,
        }
        resp = client.post("/api/tgrac/query", json=payload)
        assert resp.status_code == 200
        data = resp.json()
        assert data["type"] == "FeatureCollection"
        features = data.get("features", [])
        assert len(features) > 0
        assert len(features) <= 10
        # Check first real feature
        f0 = features[0]
        assert f0["geometry"]["type"] in ("Polygon", "MultiPolygon")
        assert "parcel_id" in f0["properties"]
        # Check provenance metadata
        prov = data.get("landsync_provenance", {})
        assert prov["source"] == "TGRAC_TELANGANA"
        assert prov["synthetic_data"] is False
        assert prov["feature_count"] == len(features)

    def test_tgrac_load_and_reconcile(self, client, monkeypatch):
        """POST /api/tgrac/load reconciles real TGRAC data and populates cache."""
        # Force DEMO_FIXTURE_MODE=false to verify production compliance
        monkeypatch.setattr(settings, "DEMO_FIXTURE_MODE", False)
        landsync_service._cache.clear()

        payload = {
            "bbox": [78.06, 17.60, 78.08, 17.62],
            "max_features": 25,
        }
        resp = client.post("/api/tgrac/load", json=payload)
        assert resp.status_code == 200
        data = resp.json()
        assert data["job_status"] == "complete"
        assert data["reconciled_parcel_count"] > 0
        assert data["provenance"]["synthetic_data_used"] is False

        # Verify parcels endpoint now returns real TGRAC parcels
        parcels_resp = client.get("/api/parcels")
        assert parcels_resp.status_code == 200
        parcels = parcels_resp.json()
        assert len(parcels) == data["reconciled_parcel_count"]
        p0 = parcels[0]
        assert p0["parcel_id"].startswith("CAD-") or p0["parcel_id"].startswith("MUN-") or len(p0["parcel_id"]) > 0

        # Verify health endpoint reports REAL_TO_REAL and TGRAC_TELANGANA
        health_resp = client.get("/api/health")
        assert health_resp.status_code == 200
        health_data = health_resp.json()
        assert health_data["engine"] == "loaded"
        assert health_data["cadastral_source"] == "TGRAC_TELANGANA"
        assert health_data["data_state"] == "REAL_TO_REAL"
