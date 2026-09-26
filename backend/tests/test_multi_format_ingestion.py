"""
backend/tests/test_multi_format_ingestion.py
============================================
Comprehensive test suite for LANDSYNC multi-format document ingestion pipeline:
GeoJSON, JSON, PDF, Images (PNG/JPG/TIFF), CAD (DXF/DWG), Shapefile ZIP,
KML/KMZ, GeoPackage, and GeoTIFF.
"""

import io
import json
import zipfile
import pytest
from pathlib import Path

from fastapi.testclient import TestClient

from backend.main import app
from backend.ingestion.router import parse_document, to_feature_collection
from backend.ingestion.models import ParsingStatus, GeometryStatus, CRSStatus
from backend.ingestion.validation import (
    validate_file_size,
    validate_and_extract_safe_zip,
)

FIXTURES_DIR = Path(__file__).resolve().parent.parent.parent / "tests" / "fixtures" / "documents"


@pytest.fixture
def client():
    return TestClient(app)


# ── 1. GeoJSON & JSON Tests ──────────────────────────────────────────────────

def test_geojson_ingestion():
    p = FIXTURES_DIR / "sample.geojson"
    res = parse_document(p)
    assert res.parsing_status == ParsingStatus.SUCCESS
    assert res.has_spatial_geometry is True
    assert len(res.parcels) == 1
    parcel = res.parcels[0]
    assert parcel.survey_number == "101/A"
    assert parcel.geometry["type"] in ("Polygon", "MultiPolygon")
    assert parcel.geometry_status == GeometryStatus.VALID_POLYGONS


def test_json_ingestion():
    p = FIXTURES_DIR / "sample.json"
    res = parse_document(p)
    assert res.parsing_status == ParsingStatus.SUCCESS
    assert res.has_spatial_geometry is True
    assert len(res.parcels) == 1


# ── 2. PDF Tests (Text & Scanned) ────────────────────────────────────────────

def test_pdf_text_extraction():
    p = FIXTURES_DIR / "sample.pdf"
    res = parse_document(p)
    assert res.parsing_status == ParsingStatus.SUCCESS
    # Text-only deed: coordinates are not fabricated!
    assert res.has_spatial_geometry is False
    assert res.geometry_status == GeometryStatus.METADATA_ONLY
    assert len(res.parcels) == 1
    parcel = res.parcels[0]
    assert "101/A" in parcel.survey_number
    assert parcel.land_use.lower() == "agricultural"
    assert parcel.classification.lower() == "patta"
    assert parcel.geometry is None
    assert res.extraction_confidence.geometry_confidence == 0.0


# ── 3. Image Tests (PNG, JPG, TIFF) ──────────────────────────────────────────

def test_image_scan_ingestion():
    for ext in ("sample_scan.png", "sample_scan.jpg", "sample_scan.tiff"):
        p = FIXTURES_DIR / ext
        res = parse_document(p)
        assert res.document_format in ("png", "jpg", "jpeg", "tiff", "tif")
        assert res.document_type == "SCANNED_IMAGE"
        assert res.has_spatial_geometry is False
        assert res.geometry_status == GeometryStatus.METADATA_ONLY
        assert len(res.parcels) == 1
        parcel = res.parcels[0]
        assert parcel.geometry is None


# ── 4. CAD Tests (DXF & DWG) ─────────────────────────────────────────────────

def test_dxf_vector_extraction():
    p = FIXTURES_DIR / "sample.dxf"
    res = parse_document(p)
    assert res.parsing_status == ParsingStatus.SUCCESS
    assert res.has_spatial_geometry is True
    assert len(res.parcels) >= 1
    parcel = res.parcels[0]
    assert parcel.geometry is not None
    assert parcel.geometry["type"] in ("Polygon", "MultiPolygon")
    assert parcel.geometry_status in (GeometryStatus.VALID_POLYGONS, GeometryStatus.REPAIRED_POLYGONS)


def test_dxf_projected_crs_required(tmp_path):
    # Create DXF with local metric coordinates (e.g. 500000, 2000000)
    import ezdxf
    doc = ezdxf.new("R2010")
    msp = doc.modelspace()
    pts = [(500000.0, 2000000.0), (500100.0, 2000000.0), (500100.0, 2000100.0), (500000.0, 2000100.0)]
    msp.add_lwpolyline(pts, close=True)
    dxf_file = tmp_path / "projected.dxf"
    doc.saveas(str(dxf_file))

    # Without crs_hint -> CRS_REQUIRED
    res_no_crs = parse_document(dxf_file)
    assert res_no_crs.parsing_status == ParsingStatus.CRS_REQUIRED
    assert res_no_crs.crs_status == CRSStatus.CRS_REQUIRED

    # With crs_hint (UTM Zone 44N = EPSG:32644) -> SUCCESS
    res_with_crs = parse_document(dxf_file, crs_hint="EPSG:32644")
    assert res_with_crs.parsing_status == ParsingStatus.SUCCESS
    assert res_with_crs.has_spatial_geometry is True


def test_dwg_honest_guidance(tmp_path):
    dwg_file = tmp_path / "cadastral.dwg"
    dwg_file.write_bytes(b"AC1032\x00\x00\x00\x00" + b"dummy dwg binary header")
    res = parse_document(dwg_file)
    assert res.parsing_status == ParsingStatus.UNSUPPORTED_FORMAT
    assert "LibreCAD" in res.errors[0] or "DXF" in res.errors[0]


# ── 5. GIS Formats (Shapefile ZIP, KML, GeoPackage) ──────────────────────────

def test_shapefile_zip_ingestion():
    p = FIXTURES_DIR / "sample_shapefile.zip"
    res = parse_document(p)
    assert res.parsing_status == ParsingStatus.SUCCESS
    assert res.has_spatial_geometry is True
    assert len(res.parcels) == 1
    assert res.parcels[0].survey_number == "101/A"


def test_kml_ingestion():
    p = FIXTURES_DIR / "sample.kml"
    res = parse_document(p)
    assert res.parsing_status == ParsingStatus.SUCCESS
    assert res.has_spatial_geometry is True
    assert len(res.parcels) == 1
    assert res.parcels[0].survey_number == "101/A"


def test_geopackage_ingestion():
    p = FIXTURES_DIR / "sample.gpkg"
    res = parse_document(p)
    assert res.parsing_status == ParsingStatus.SUCCESS
    assert res.has_spatial_geometry is True
    assert len(res.parcels) == 1


# ── 6. Security & Guardrails ─────────────────────────────────────────────────

def test_path_traversal_zip_slip_protection(tmp_path):
    zip_path = tmp_path / "malicious.zip"
    with zipfile.ZipFile(zip_path, "w") as zf:
        zf.writestr("../../etc/passwd", "evil content")

    dest_dir = tmp_path / "extract"
    dest_dir.mkdir()
    with pytest.raises(ValueError, match="Path traversal detected"):
        validate_and_extract_safe_zip(zip_path, dest_dir)


def test_archive_bomb_protection(tmp_path):
    zip_path = tmp_path / "bomb.zip"
    with zipfile.ZipFile(zip_path, "w", compression=zipfile.ZIP_DEFLATED) as zf:
        # 10 MB of zeros compresses into < 10 KB (ratio > 1000)
        zf.writestr("zeroes.bin", b"\x00" * (10 * 1024 * 1024))

    dest_dir = tmp_path / "extract_bomb"
    dest_dir.mkdir()
    with pytest.raises(ValueError, match="archive bomb"):
        validate_and_extract_safe_zip(zip_path, dest_dir)


def test_oversized_file_protection(tmp_path):
    big_file = tmp_path / "huge.geojson"
    big_file.write_bytes(b"A" * 100)
    with pytest.raises(ValueError, match="exceeds maximum"):
        validate_file_size(big_file, max_bytes=50)


# ── 7. Full API Upload & Reconciliation Pipeline ─────────────────────────────

def test_api_upload_shapefile_and_kml(client):
    shp_path = FIXTURES_DIR / "sample_shapefile.zip"
    kml_path = FIXTURES_DIR / "sample.kml"

    with open(shp_path, "rb") as f1, open(kml_path, "rb") as f2:
        resp = client.post(
            "/api/upload",
            files=[
                ("files", ("cadastral.zip", f1, "application/zip")),
                ("files", ("municipal.kml", f2, "application/vnd.google-earth.kml+xml")),
            ],
        )

    assert resp.status_code == 200
    data = resp.json()
    assert "dataset_id" in data
    assert data["files_received"] == 2
    assert len(data["parsing_summaries"]) == 2
    assert data["ready_for_reconciliation"] is True

    # Process uploaded multi-format dataset through reconciliation engine
    proc_resp = client.post("/api/process", json={"dataset_id": data["dataset_id"]})
    assert proc_resp.status_code == 200
    assert proc_resp.json()["job_status"] == "complete"

    # Verify /api/parcels returns the reconciled parcel
    parcels_resp = client.get("/api/parcels")
    assert parcels_resp.status_code == 200
    parcels = parcels_resp.json()
    assert len(parcels) >= 1


def test_api_upload_pdf_text_record(client):
    pdf_path = FIXTURES_DIR / "sample.pdf"
    with open(pdf_path, "rb") as f:
        resp = client.post(
            "/api/upload",
            files=[("file", ("deed.pdf", f, "application/pdf"))],
        )

    assert resp.status_code == 200
    data = resp.json()
    summary = data["parsing_summaries"][0]
    assert summary["format"] == "pdf"
    assert summary["geometry_status"] == "METADATA_ONLY"
    assert summary["has_spatial_geometry"] is False
    assert data["ready_for_reconciliation"] is False
    assert "Spatial boundaries were not found" in data["notice"]


def test_api_upload_dxf_cad(client):
    dxf_path = FIXTURES_DIR / "sample.dxf"
    with open(dxf_path, "rb") as f:
        resp = client.post(
            "/api/upload",
            files=[("file", ("cadastral.dxf", f, "application/dxf"))],
        )

    assert resp.status_code == 200
    data = resp.json()
    summary = data["parsing_summaries"][0]
    assert summary["format"] == "dxf"
    assert summary["has_spatial_geometry"] is True
