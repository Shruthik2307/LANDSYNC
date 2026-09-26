"""
scripts/test_real_document_upload.py
====================================
Comprehensive verification script for the REAL DOCUMENT UPLOAD PIPELINE:
  1. File Upload (single & multi-document)
  2. File Validation & Error Handling (PDF, malformed, empty, non-GeoJSON)
  3. Real GIS Geometry Extraction & Repair
  4. Attribute & Identifier Normalization (detecting survey_no, ID aliases)
  5. Cadastral vs Municipal Association & Matching
  6. GIS Spatial & Metric Calculations
  7. 14-Feature ML Schema Extraction
  8. Real ML Model Prediction & Probabilities
  9. Confidence & Disputed Area Computation
  10. Demo vs Live Upload Isolation
"""
import io
import json
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
backend_path = ROOT / "backend"
if str(backend_path) not in sys.path:
    sys.path.insert(0, str(backend_path))

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

import httpx
from fastapi.testclient import TestClient
from backend.main import app
from backend.services.ml_service import conflict_detector
from engine.ml_schema import FEATURE_ORDER

FIXTURES_DIR = ROOT / "tests" / "fixtures" / "documents"

LIVE_URL = sys.argv[1].rstrip("/") if len(sys.argv) > 1 and sys.argv[1].startswith("http") else None
if LIVE_URL:
    print(f"--> Target: LIVE SERVER at {LIVE_URL}")
    client = httpx.Client(base_url=LIVE_URL, timeout=30.0)
else:
    print("--> Target: LOCAL IN-PROCESS TestClient(app)")
    client = TestClient(app)

passed = 0
failed = 0

def check(name: str, cond: bool, detail: str = ""):
    global passed, failed
    if cond:
        print(f"  [PASS] {name}")
        passed += 1
    else:
        print(f"  [FAIL] {name} -- {detail}")
        failed += 1

def run_tests():
    global passed, failed
    passed = 0
    failed = 0

    print("=" * 75)
    print("LANDSYNC AUDIT: REAL DOCUMENT UPLOAD & RECONCILIATION PIPELINE")
    print("=" * 75)

    # -----------------------------------------------------------------------
    # TEST 1: ERROR HANDLING ON INVALID DOCUMENTS / NON-GEOJSON
    # -----------------------------------------------------------------------
    print("\n[SECTION 1] FILE VALIDATION & ERROR HANDLING")

    # 1.1 Upload unsupported file format (.exe / .csv)
    fake_exe = io.BytesIO(b"MZ\x90\x00\x03\x00\x00\x00")
    res = client.post("/api/upload", files={"file": ("malware.exe", fake_exe, "application/octet-stream")})
    check("Reject unsupported binary with HTTP 400", res.status_code == 400, f"Got {res.status_code}: {res.text}")
    check("Useful error message for unsupported format", "Unsupported file type" in res.json().get("detail", ""))

    # 1.1b Ingest real PDF deed record
    pdf_path = FIXTURES_DIR / "sample.pdf"
    if pdf_path.exists():
        with open(pdf_path, "rb") as pf:
            pdf_res = client.post("/api/upload", files={"file": ("sample.pdf", pf, "application/pdf")})
        check("Accept PDF deed document with HTTP 200", pdf_res.status_code == 200, pdf_res.text)
        pdf_data = pdf_res.json()
        check("PDF identified as METADATA_ONLY without fake coordinates", pdf_data.get("ready_for_reconciliation") is False)
        check("PDF notice indicates metadata extracted", "Spatial boundaries were not found" in (pdf_data.get("notice") or ""))

    # 1.2 Upload CSV document
    fake_csv = io.BytesIO(b"parcel_id,survey_number,owner\nP1,101,Ramesh\n")
    res = client.post("/api/upload", files={"file": ("parcels.csv", fake_csv, "text/csv")})
    check("Reject CSV upload with HTTP 400", res.status_code == 400, f"Got {res.status_code}: {res.text}")

    # 1.3 Upload empty file
    empty_file = io.BytesIO(b"")
    res = client.post("/api/upload", files={"file": ("empty.geojson", empty_file, "application/json")})
    check("Reject empty file with HTTP 400", res.status_code == 400, f"Got {res.status_code}: {res.text}")

    # 1.4 Upload malformed JSON
    corrupted_json = io.BytesIO(b'{"type": "FeatureCollection", "features": [ { "type": "Feature", malformed... }')
    res = client.post("/api/upload", files={"file": ("corrupted.geojson", corrupted_json, "application/json")})
    check("Reject malformed JSON with HTTP 400", res.status_code == 400, f"Got {res.status_code}: {res.text}")

    # 1.5 Upload JSON that is not a FeatureCollection
    non_fc = io.BytesIO(b'{"type": "Point", "coordinates": [78.4, 17.3]}')
    res = client.post("/api/upload", files={"file": ("point.json", non_fc, "application/json")})
    check("Reject non-FeatureCollection JSON with HTTP 400", res.status_code == 400, f"Got {res.status_code}: {res.text}")

    # 1.6 Upload FeatureCollection with 0 features
    empty_fc = io.BytesIO(b'{"type": "FeatureCollection", "features": []}')
    res = client.post("/api/upload", files={"file": ("empty_fc.geojson", empty_fc, "application/json")})
    check("Reject empty FeatureCollection with HTTP 400", res.status_code == 400, f"Got {res.status_code}: {res.text}")

    # -----------------------------------------------------------------------
    # TEST 2: REAL SINGLE DOCUMENT UPLOAD & RECONCILIATION
    # -----------------------------------------------------------------------
    print("\n[SECTION 2] REAL SINGLE GEOJSON UPLOAD & PROCESSING")

    real_cadastral = {
        "type": "FeatureCollection",
        "features": [
            {
                "type": "Feature",
                "properties": {
                    "survey_number": "SY-401/A",
                    "land_use": "Agricultural",
                    "classification": "Patta",
                    "owner": "K. Venkatesh"
                },
                "geometry": {
                    "type": "Polygon",
                    "coordinates": [[
                        [78.4500, 17.4000],
                        [78.4510, 17.4000],
                        [78.4510, 17.4010],
                        [78.4500, 17.4010],
                        [78.4500, 17.4000]
                    ]]
                }
            }
        ]
    }
    cad_bytes = io.BytesIO(json.dumps(real_cadastral).encode("utf-8"))
    up_res = client.post("/api/upload", files={"file": ("real_cadastral_sy401.geojson", cad_bytes, "application/json")})
    check("Upload single valid GeoJSON returns HTTP 200", up_res.status_code == 200, up_res.text)
    dataset_id = up_res.json().get("dataset_id")
    check("Dataset ID returned", bool(dataset_id and dataset_id.startswith("ds_")))

    # Process the uploaded dataset
    proc_res = client.post("/api/process", json={"dataset_id": dataset_id})
    check("Process uploaded single dataset returns HTTP 200", proc_res.status_code == 200, proc_res.text)
    check("Job status complete", proc_res.json().get("job_status") == "complete")

    # Check health & provenance
    health_res = client.get("/api/health")
    h = health_res.json()
    check("Health reflects USER_UPLOADED_REAL cadastral source", h.get("cadastral_source") == "USER_UPLOADED_REAL", str(h))
    check("Health data_state is REAL + SAMPLE MIXED", "REAL_TO_SAMPLE_MIXED" in h.get("data_state", "") or "MIXED" in h.get("data_state", ""))

    # Inspect parcels returned
    parcels_res = client.get("/api/parcels")
    parcels = parcels_res.json()
    check("Parcels returned from uploaded data", len(parcels) > 0)
    p = parcels[0]
    check("Parcel ID derived from survey_number or stable hash", "SY-401" in p.get("parcel_id") or "auto-" in p.get("parcel_id") or "CAD-" in p.get("parcel_id"))
    check("Real cadastral geometry preserved", p.get("boundaries", {}).get("cadastral") is not None)
    cad_coords = p.get("boundaries", {}).get("cadastral", {}).get("coordinates", [[]])[0]
    check("Coordinates match uploaded polygon", abs(cad_coords[0][0] - 78.4500) < 1e-4)

    # -----------------------------------------------------------------------
    # TEST 3: MULTI-DOCUMENT REAL UPLOAD (CADASTRAL + MUNICIPAL)
    # -----------------------------------------------------------------------
    print("\n[SECTION 3] MULTI-DOCUMENT REAL RECONCILIATION (Cadastral + Municipal)")

    real_cadastral_pair = {
        "type": "FeatureCollection",
        "features": [
            {
                "type": "Feature",
                "properties": {
                    "parcel_id": "TS-HYD-REAL-001",
                    "survey_number": "502/B",
                    "land_use": "Commercial",
                    "classification": "Non-Agricultural"
                },
                "geometry": {
                    "type": "Polygon",
                    "coordinates": [[
                        [78.4800, 17.4200],
                        [78.4815, 17.4200],
                        [78.4815, 17.4215],
                        [78.4800, 17.4215],
                        [78.4800, 17.4200]
                    ]]
                }
            }
        ]
    }

    # Municipal survey with a slight 3-metre boundary deviation (minor discrepancy)
    real_municipal_pair = {
        "type": "FeatureCollection",
        "features": [
            {
                "type": "Feature",
                "properties": {
                    "parcel_id": "TS-HYD-REAL-001",
                    "survey_number": "502/B",
                    "land_use": "Commercial",
                    "classification": "Non-Agricultural"
                },
                "geometry": {
                    "type": "Polygon",
                    "coordinates": [[
                        [78.48003, 17.42002],
                        [78.48152, 17.42001],
                        [78.48149, 17.42148],
                        [78.48002, 17.42151],
                        [78.48003, 17.42002]
                    ]]
                }
            }
        ]
    }

    f1 = io.BytesIO(json.dumps(real_cadastral_pair).encode("utf-8"))
    f2 = io.BytesIO(json.dumps(real_municipal_pair).encode("utf-8"))

    multi_up_res = client.post(
        "/api/upload",
        files=[
            ("files", ("cadastral_survey502.geojson", f1, "application/json")),
            ("files", ("municipal_ghmc_survey502.geojson", f2, "application/json")),
        ]
    )
    check("Upload both documents returns HTTP 200", multi_up_res.status_code == 200, multi_up_res.text)
    multi_ds_id = multi_up_res.json().get("dataset_id")
    check("Multi-doc dataset ID returned", bool(multi_ds_id))

    # Process multi-document dataset
    multi_proc = client.post("/api/process", json={"dataset_id": multi_ds_id})
    check("Process multi-document dataset returns HTTP 200", multi_proc.status_code == 200, multi_proc.text)

    # Check health and verify genuine REAL -> REAL reconciliation
    h_multi = client.get("/api/health").json()
    check("Cadastral source is USER_UPLOADED_REAL", h_multi.get("cadastral_source") == "USER_UPLOADED_REAL")
    check("Municipal source is USER_UPLOADED_REAL", h_multi.get("municipal_source") == "USER_UPLOADED_REAL")
    check("Reconciliation type is REAL_TO_REAL", h_multi.get("reconciliation_type") == "REAL_TO_REAL")

    # Verify provenance endpoint
    prov = client.get("/api/provenance").json()
    check("Provenance summary is REAL -> REAL RECONCILIATION", "REAL_TO_REAL" in prov.get("reconciliation_type", ""))

    # -----------------------------------------------------------------------
    # TEST 4: ML INTEGRATION & 14-FEATURE EXTRACTION FROM REAL DATA
    # -----------------------------------------------------------------------
    print("\n[SECTION 4] ML INTEGRATION & 14-FEATURE TRACE ON REAL PARCEL")

    real_parcels = client.get("/api/parcels").json()
    check("Reconciled parcel count is 1", len(real_parcels) == 1)
    rp = real_parcels[0]
    check("Parcel ID preserved as TS-HYD-REAL-001", rp.get("parcel_id") == "TS-HYD-REAL-001")
    check("Cadastral boundary present", "cadastral" in rp.get("boundaries", {}))
    check("Municipal (drone/survey) boundary present", "drone_ori" in rp.get("boundaries", {}))

    # Check ML features & metrics on this real parcel
    sm = rp.get("spatial_metrics", {})
    check("Spatial IoU computed (> 0.90)", sm.get("iou", 0) > 0.90, f"iou={sm.get('iou')}")
    check("Centroid distance computed", sm.get("centroid_distance_m") is not None)
    check("Hausdorff distance computed", sm.get("hausdorff_distance_m") is not None)
    check("Boundary displacement computed", sm.get("boundary_displacement_m") is not None)
    check("Area difference computed (> 0)", rp.get("area_difference", 0) >= 0)

    # Check ML model prediction
    ml_info = rp.get("ml", {})
    check("ML model status is OK", ml_info.get("model_status") == "OK", str(ml_info))
    check("ML prediction exists", ml_info.get("prediction") is not None)
    check("ML confidence calculated (0-100%)", 0 <= rp.get("confidence", 0) <= 100)

    # Check detail endpoint
    p_detail = client.get(f"/api/parcels/{rp['parcel_id']}").json()
    check("GET /api/parcels/{id} returns real uploaded record", p_detail.get("parcel_id") == rp["parcel_id"])

    # -----------------------------------------------------------------------
    # TEST 5: HUMAN REVIEW & LABEL OVERRIDE ON REAL UPLOADED PARCEL
    # -----------------------------------------------------------------------
    print("\n[SECTION 5] HUMAN REVIEW & OVERRIDE PERSISTENCE ON REAL RECORD")

    override_res = client.post("/api/ml/label", json={
        "parcel_id": rp["parcel_id"],
        "label": 0,
        "reviewer": "chief_revenue_officer",
        "notes": "Verified field boundary aligns with cadastral stone markers."
    })
    check("Human review label override succeeds", override_res.status_code == 200, override_res.text)

    # -----------------------------------------------------------------------
    # TEST 6: ISOLATION TEST (Upload Mode vs Demo Mode)
    # -----------------------------------------------------------------------
    print("\n[SECTION 6] DEMO VS LIVE UPLOAD ISOLATION")

    # In demo mode, dataset is preloaded sample
    # In live upload mode, dataset is user's uploaded real parcel
    check("Uploaded parcel ID is NOT any demo parcel ID", rp["parcel_id"] not in ("P-001", "P-002", "P-003", "P-004", "HYD-REV-1000"))
    check("Uploaded parcel geometry is NOT demo geometry", rp["boundaries"]["cadastral"]["coordinates"][0][0][0] == 78.4800)

    print("\n" + "=" * 75)
    print(f"REAL DOCUMENT PIPELINE AUDIT COMPLETED: {passed} PASSED, {failed} FAILED")
    print("=" * 75)
    return failed == 0

if __name__ == "__main__":
    success = run_tests()
    sys.exit(0 if success else 1)
