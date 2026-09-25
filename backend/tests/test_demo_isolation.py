"""
backend/tests/test_demo_isolation.py
====================================
Spec §7 regression tests: synthetic fixtures (data/sample/*) may load ONLY
when DEMO_FIXTURE_MODE=true. With DEMO_FIXTURE_MODE=false (production) the
API must surface an explicit REAL_DATA_UNAVAILABLE state instead of silently
substituting synthetic parcels.
"""

from __future__ import annotations

import pytest

from config import settings


@pytest.fixture()
def production_mode(monkeypatch):
    """Force DEMO_FIXTURE_MODE=false and clear any loaded cache."""
    from services import landsync_service

    monkeypatch.setattr(settings, "DEMO_FIXTURE_MODE", False)
    landsync_service._cache.clear()
    yield
    landsync_service._cache.clear()


@pytest.fixture()
def demo_mode(monkeypatch):
    """Force DEMO_FIXTURE_MODE=true and clear any loaded cache."""
    from services import landsync_service

    monkeypatch.setattr(settings, "DEMO_FIXTURE_MODE", True)
    landsync_service._cache.clear()
    yield
    landsync_service._cache.clear()


class TestDemoFixtureIsolation:
    def test_health_reports_real_data_unavailable_when_unloaded(self, client, production_mode):
        """Unloaded + production → health must say REAL_DATA_UNAVAILABLE."""
        resp = client.get("/api/health")
        assert resp.status_code == 200
        data = resp.json()
        assert data["engine"] == "unavailable"
        assert data["data_state"] == "REAL_DATA_UNAVAILABLE"
        assert data["demo_fixture_mode"] is False

    def test_parcels_rejects_silent_sample_load_in_production(self, client, production_mode):
        """GET /api/parcels must NOT auto-load synthetic sample in production."""
        resp = client.get("/api/parcels")
        assert resp.status_code == 503
        assert "REAL_DATA_UNAVAILABLE" in resp.json()["detail"]

    def test_conflicts_rejects_silent_sample_load_in_production(self, client, production_mode):
        """GET /api/conflicts must NOT auto-load synthetic sample in production."""
        resp = client.get("/api/conflicts")
        assert resp.status_code == 503
        assert "REAL_DATA_UNAVAILABLE" in resp.json()["detail"]

    def test_process_rejects_sample_dataset_in_production(self, client, production_mode):
        """POST /api/process with the built-in sample id is blocked in production."""
        resp = client.post("/api/process", json={"dataset_id": "sample"})
        assert resp.status_code == 422
        assert "REAL_DATA_UNAVAILABLE" in resp.json()["detail"]

    def test_demo_mode_autoloads_sample_fixtures(self, client, demo_mode):
        """GET /api/parcels auto-loads the synthetic sample in demo mode."""
        resp = client.get("/api/parcels")
        assert resp.status_code == 200
        assert len(resp.json()) > 0

    def test_health_reports_synthetic_state_in_demo_mode(self, client, demo_mode):
        """Loaded sample + demo mode → health reports SYNTHETIC_DEMO_DATA."""
        client.get("/api/parcels")  # trigger demo auto-load
        data = client.get("/api/health").json()
        assert data["demo_fixture_mode"] is True
        assert data["data_state"] == "SYNTHETIC_DEMO_DATA"
        assert data["cadastral_source"] == "SYNTHETIC_DEMO"
        assert data["municipal_source"] == "SYNTHETIC_DEMO"
