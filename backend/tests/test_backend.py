"""
backend/tests/test_backend.py
==============================
Backend integration tests for the LANDSYNC FastAPI server.

Tests cover:
    1. GET  /api/health          — returns 200, status field, engine info
    2. Loading municipal.geojson — 25 features, CRS validation
    3. GET  /api/parcels         — 25 parcels, correct schema
    4. GET  /api/parcels/{id}    — valid parcel returned
    5. GET  /api/parcels/NONE    — 404 for unknown parcel
    6. GET  /api/conflicts       — only conflict parcels, sorted HIGH first
    7. POST /api/process         — returns { job_status: "complete" }
    8. POST /api/upload          — valid GeoJSON accepted
    9. POST /api/upload          — invalid file rejected with 400
   10. Parcel schema compliance  — all required fields present with correct types
"""

from __future__ import annotations

import io
import json
import sys
from pathlib import Path

import pytest

# ---------------------------------------------------------------------------
# Ensure sys.path includes project root and backend/ (redundant if conftest
# already ran, but safe to repeat).
# ---------------------------------------------------------------------------
_TESTS_DIR = Path(__file__).resolve().parent
_BACKEND_DIR = _TESTS_DIR.parent
_PROJECT_ROOT = _BACKEND_DIR.parent
for _p in (_PROJECT_ROOT, _BACKEND_DIR):
    if str(_p) not in sys.path:
        sys.path.insert(0, str(_p))

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------
EXPECTED_PARCEL_COUNT = 25
VALID_PARCEL_ID = "HYD-REV-1000"
INVALID_PARCEL_ID = "NONEXISTENT-9999"
PRIORITY_ORDER = {"HIGH": 0, "MEDIUM": 1, "LOW": 2}
REQUIRED_PARCEL_KEYS = {
    "parcel_id",
    "confidence",
    "priority",
    "area_difference",
    "geometry_conflict",
    "attribute_conflict",
    "duplicate_id",
    "recommendation",
    "boundaries",
}


# ===========================================================================
# 1. Health endpoint
# ===========================================================================

class TestHealth:
    def test_health_returns_200(self, client):
        """GET /api/health must return HTTP 200."""
        resp = client.get("/api/health")
        assert resp.status_code == 200

    def test_health_status_field(self, client):
        """Health response must include a 'status' field."""
        data = client.get("/api/health").json()
        assert "status" in data
        assert data["status"] in {"ok", "degraded"}

    def test_health_engine_loaded_after_startup(self, client):
        """Engine should be loaded after startup pre-load."""
        data = client.get("/api/health").json()
        # After a successful startup the engine should be 'loaded'
        assert data.get("engine") == "loaded"

    def test_health_includes_parcel_count(self, client):
        """Health response must include parcel_count when engine is loaded."""
        data = client.get("/api/health").json()
        if data.get("engine") == "loaded":
            assert isinstance(data["parcel_count"], int)
            assert data["parcel_count"] > 0

    def test_health_reports_crs(self, client):
        """Health response must report the engine CRS (EPSG:3857)."""
        data = client.get("/api/health").json()
        if data.get("engine") == "loaded":
            assert data.get("engine_crs") == "EPSG:3857"


# ===========================================================================
# 2. Municipal GeoJSON loading
# ===========================================================================

class TestMunicipalGeoJSON:
    def test_municipal_geojson_exists(self, sample_data_dir):
        """data/sample/municipal.geojson must exist."""
        path = sample_data_dir / "municipal.geojson"
        assert path.exists(), f"File not found: {path}"

    def test_municipal_geojson_is_valid_json(self, sample_data_dir):
        """municipal.geojson must be valid JSON."""
        path = sample_data_dir / "municipal.geojson"
        with open(path, encoding="utf-8") as f:
            data = json.load(f)
        assert data["type"] == "FeatureCollection"

    def test_municipal_geojson_has_25_features(self, sample_data_dir):
        """municipal.geojson must contain exactly 25 features."""
        path = sample_data_dir / "municipal.geojson"
        with open(path, encoding="utf-8") as f:
            data = json.load(f)
        assert len(data["features"]) == EXPECTED_PARCEL_COUNT

    def test_municipal_geojson_has_parcel_id_field(self, sample_data_dir):
        """Every feature in municipal.geojson must have a parcel_id property."""
        path = sample_data_dir / "municipal.geojson"
        with open(path, encoding="utf-8") as f:
            data = json.load(f)
        for feature in data["features"]:
            props = feature.get("properties", {})
            assert "parcel_id" in props, f"Feature missing parcel_id: {props}"

    def test_municipal_geojson_crs_is_wgs84(self, sample_data_dir):
        """municipal.geojson CRS should be WGS84 / CRS84."""
        import geopandas as gpd
        gdf = gpd.read_file(sample_data_dir / "municipal.geojson")
        # CRS should be parseable by pyproj
        assert gdf.crs is not None
        # Should be geographic (lat/lon), not projected
        epsg = gdf.crs.to_epsg()
        # CRS84 is equivalent to EPSG:4326 for 2D use
        assert epsg in {4326, None}, (
            f"Expected EPSG:4326 (WGS84), got EPSG:{epsg}. "
            "Note: CRS84 axis-order variant may return None from to_epsg()."
        )


# ===========================================================================
# 3. GET /api/parcels — list all parcels
# ===========================================================================

class TestParcels:
    def test_parcels_returns_200(self, client):
        """GET /api/parcels must return HTTP 200."""
        resp = client.get("/api/parcels")
        assert resp.status_code == 200

    def test_parcels_is_list(self, client):
        """GET /api/parcels must return a JSON array."""
        data = client.get("/api/parcels").json()
        assert isinstance(data, list)

    def test_parcels_count(self, client):
        """GET /api/parcels must return exactly 25 parcels (sample dataset)."""
        data = client.get("/api/parcels").json()
        assert len(data) == EXPECTED_PARCEL_COUNT, (
            f"Expected {EXPECTED_PARCEL_COUNT} parcels, got {len(data)}"
        )

    def test_parcels_schema_compliance(self, client):
        """Every parcel must contain all required keys."""
        parcels = client.get("/api/parcels").json()
        for parcel in parcels:
            missing = REQUIRED_PARCEL_KEYS - set(parcel.keys())
            assert not missing, (
                f"Parcel {parcel.get('parcel_id')} is missing keys: {missing}"
            )

    def test_parcels_confidence_range(self, client):
        """Confidence must be in [0, 100] for every parcel."""
        for p in client.get("/api/parcels").json():
            assert 0 <= p["confidence"] <= 100, (
                f"Parcel {p['parcel_id']}: confidence={p['confidence']} out of range"
            )

    def test_parcels_priority_values(self, client):
        """Priority must be HIGH, MEDIUM, or LOW for every parcel."""
        valid = {"HIGH", "MEDIUM", "LOW"}
        for p in client.get("/api/parcels").json():
            assert p["priority"] in valid, (
                f"Parcel {p['parcel_id']}: invalid priority={p['priority']!r}"
            )

    def test_parcels_boundaries_cadastral_present(self, client):
        """boundaries.cadastral must be present for every parcel."""
        for p in client.get("/api/parcels").json():
            assert "cadastral" in p.get("boundaries", {}), (
                f"Parcel {p['parcel_id']}: boundaries.cadastral missing"
            )

    def test_parcels_boundaries_are_polygons(self, client):
        """boundaries.cadastral must be a GeoJSON Polygon."""
        for p in client.get("/api/parcels").json():
            cad = p["boundaries"]["cadastral"]
            assert cad["type"] == "Polygon", (
                f"Parcel {p['parcel_id']}: cadastral boundary type={cad['type']!r}"
            )

    def test_parcels_conflict_boundary_has_drone_ori(self, client):
        """Parcels with geometry_conflict=True must have boundaries.drone_ori."""
        for p in client.get("/api/parcels").json():
            if p["geometry_conflict"]:
                assert "drone_ori" in p["boundaries"], (
                    f"Parcel {p['parcel_id']}: geometry_conflict=True "
                    "but boundaries.drone_ori is missing"
                )

    def test_parcels_types_are_correct(self, client):
        """Verify Python types for key fields."""
        for p in client.get("/api/parcels").json():
            assert isinstance(p["parcel_id"], str)
            assert isinstance(p["confidence"], int)
            assert isinstance(p["area_difference"], (int, float))
            assert isinstance(p["geometry_conflict"], bool)
            assert isinstance(p["attribute_conflict"], bool)
            assert isinstance(p["duplicate_id"], bool)
            assert isinstance(p["recommendation"], str)


# ===========================================================================
# 4. GET /api/parcels/{parcel_id}
# ===========================================================================

class TestParcelById:
    def test_valid_parcel_returns_200(self, client):
        """GET /api/parcels/HYD-REV-1000 must return 200."""
        resp = client.get(f"/api/parcels/{VALID_PARCEL_ID}")
        assert resp.status_code == 200

    def test_valid_parcel_has_correct_id(self, client):
        """The returned parcel must have the requested parcel_id."""
        data = client.get(f"/api/parcels/{VALID_PARCEL_ID}").json()
        assert data["parcel_id"] == VALID_PARCEL_ID

    def test_unknown_parcel_returns_404(self, client):
        """GET /api/parcels/NONEXISTENT must return 404."""
        resp = client.get(f"/api/parcels/{INVALID_PARCEL_ID}")
        assert resp.status_code == 404

    def test_404_has_detail_field(self, client):
        """404 response must include a 'detail' field."""
        data = client.get(f"/api/parcels/{INVALID_PARCEL_ID}").json()
        assert "detail" in data


# ===========================================================================
# 5. GET /api/conflicts
# ===========================================================================

class TestConflicts:
    def test_conflicts_returns_200(self, client):
        """GET /api/conflicts must return HTTP 200."""
        resp = client.get("/api/conflicts")
        assert resp.status_code == 200

    def test_conflicts_is_list(self, client):
        """GET /api/conflicts must return a JSON array."""
        data = client.get("/api/conflicts").json()
        assert isinstance(data, list)

    def test_conflicts_all_have_conflicts(self, client):
        """Every conflict parcel must have at least one conflict flag set."""
        for p in client.get("/api/conflicts").json():
            has_conflict = (
                p["geometry_conflict"]
                or p["attribute_conflict"]
                or p["duplicate_id"]
            )
            assert has_conflict, (
                f"Parcel {p['parcel_id']} has no conflict flags but appears "
                "in /api/conflicts"
            )

    def test_conflicts_sorted_high_first(self, client):
        """Conflicts must appear in priority order (HIGH before MEDIUM/LOW)."""
        conflicts = client.get("/api/conflicts").json()
        if len(conflicts) < 2:
            pytest.skip("Not enough conflicts to test ordering")
        priorities = [p["priority"] for p in conflicts]
        orders = [PRIORITY_ORDER[pr] for pr in priorities]
        assert orders == sorted(orders), (
            f"Conflicts not sorted by priority. Got: {priorities}"
        )

    def test_conflicts_subset_of_parcels(self, client):
        """All conflict parcel IDs must appear in /api/parcels."""
        all_ids = {p["parcel_id"] for p in client.get("/api/parcels").json()}
        for p in client.get("/api/conflicts").json():
            assert p["parcel_id"] in all_ids, (
                f"Conflict parcel {p['parcel_id']!r} not found in /api/parcels"
            )


# ===========================================================================
# 6. POST /api/process
# ===========================================================================

class TestProcess:
    def test_process_returns_200(self, client):
        """POST /api/process must return HTTP 200."""
        resp = client.post("/api/process", json={"dataset_id": "test-ds-001"})
        assert resp.status_code == 200

    def test_process_job_status_complete(self, client):
        """POST /api/process must return job_status='complete' for valid request."""
        data = client.post("/api/process", json={"dataset_id": "test-ds-001"}).json()
        assert data.get("job_status") == "complete"

    def test_process_missing_dataset_id_returns_422(self, client):
        """POST /api/process without dataset_id must return 422 (validation error)."""
        resp = client.post("/api/process", json={})
        assert resp.status_code == 422


# ===========================================================================
# 7. POST /api/upload
# ===========================================================================

class TestUpload:
    def _make_geojson_file(self, n_features: int = 3) -> tuple[str, bytes]:
        """Build a minimal valid GeoJSON FeatureCollection."""
        features = [
            {
                "type": "Feature",
                "properties": {"parcel_id": f"TEST-{i:04d}"},
                "geometry": {
                    "type": "Polygon",
                    "coordinates": [[[78.5, 17.4], [78.51, 17.4], [78.51, 17.41], [78.5, 17.41], [78.5, 17.4]]],
                },
            }
            for i in range(n_features)
        ]
        geojson = json.dumps({"type": "FeatureCollection", "features": features})
        return "test.geojson", geojson.encode()

    def test_valid_geojson_upload_returns_200(self, client):
        """POST /api/upload with valid GeoJSON must return 200."""
        filename, content = self._make_geojson_file()
        resp = client.post(
            "/api/upload",
            files={"file": (filename, io.BytesIO(content), "application/geo+json")},
        )
        assert resp.status_code == 200

    def test_valid_upload_has_dataset_id(self, client):
        """POST /api/upload response must include a dataset_id."""
        filename, content = self._make_geojson_file()
        data = client.post(
            "/api/upload",
            files={"file": (filename, io.BytesIO(content), "application/geo+json")},
        ).json()
        assert "dataset_id" in data
        assert isinstance(data["dataset_id"], str)
        assert len(data["dataset_id"]) > 0

    def test_invalid_extension_returns_400(self, client):
        """POST /api/upload with a .txt file must return 400."""
        resp = client.post(
            "/api/upload",
            files={"file": ("data.txt", io.BytesIO(b"not geojson"), "text/plain")},
        )
        assert resp.status_code == 400

    def test_empty_file_returns_400(self, client):
        """POST /api/upload with an empty file must return 400."""
        resp = client.post(
            "/api/upload",
            files={"file": ("empty.geojson", io.BytesIO(b""), "application/geo+json")},
        )
        assert resp.status_code == 400

    def test_invalid_json_returns_400(self, client):
        """POST /api/upload with malformed JSON must return 400."""
        resp = client.post(
            "/api/upload",
            files={"file": ("bad.geojson", io.BytesIO(b"{malformed"), "application/geo+json")},
        )
        assert resp.status_code == 400

    def test_wrong_geojson_type_returns_400(self, client):
        """POST /api/upload with non-FeatureCollection GeoJSON must return 400."""
        bad = json.dumps({"type": "Point", "coordinates": [78.5, 17.4]}).encode()
        resp = client.post(
            "/api/upload",
            files={"file": ("pt.geojson", io.BytesIO(bad), "application/geo+json")},
        )
        assert resp.status_code == 400


class TestExportEndpoints:
    def test_export_geojson_success(self, client):
        """GET /api/export?dataset_id=sample returns FeatureCollection with parcels (G1/G3)."""
        resp = client.get("/api/export?dataset_id=sample")
        assert resp.status_code == 200
        assert "application/geo+json" in resp.headers.get("content-type", "")
        data = resp.json()
        assert data.get("type") == "FeatureCollection"
        features = data.get("features", [])
        assert len(features) == 25
        first = features[0]
        assert first["type"] == "Feature"
        assert "geometry" in first
        assert "properties" in first
        assert "parcel_id" in first["properties"]
