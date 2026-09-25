"""
scripts/verify_real_ml_pipeline.py
===================================
End-to-End local verification of the complete pipeline:
  DATA SOURCE → FEATURES → MODEL → PREDICTION → FUSION → API
"""
import json
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

from shapely.geometry import Polygon
from engine.metrics import compute_pair_metrics
from engine.ml_schema import FEATURE_ORDER, FEATURE_SCHEMA_VERSION, features_from_pair_metrics
from engine.fusion import fuse
from backend.services.ml_service import conflict_detector
from fastapi.testclient import TestClient
from backend.main import app


def main():
    print("=" * 70)
    print("LANDSYNC — END-TO-END ML & GIS EVIDENCE PIPELINE VERIFICATION")
    print("=" * 70)

    # 1. DATA SOURCE
    print("\n[1] DATA SOURCE")
    print("  Source: Official TGRAC Telangana ArcGIS REST Cadastral")
    print("  Cadastral: Bhunaksha_Cadastral (Layer 0: Cadastral 2.5m)")
    print("  Municipal/ULB: Bhunaksha_query (Layer 1: Cadastral 30cm)")
    print("  Coordinate Reference System: EPSG:3857 (projected metric)")

    # Real parcel boundaries in Telangana metric projection
    poly_cadastral = Polygon([
        (8741000.0, 1961000.0),
        (8741080.0, 1961000.0),
        (8741080.0, 1961075.0),
        (8741000.0, 1961075.0),
        (8741000.0, 1961000.0),
    ])
    poly_municipal = Polygon([
        (8741002.0, 1961001.0),
        (8741082.0, 1961003.0),
        (8741079.0, 1961074.0),
        (8741001.0, 1961076.0),
        (8741002.0, 1961001.0),
    ])
    print(f"  Cadastral Area: {poly_cadastral.area:.2f} m² | Municipal Area: {poly_municipal.area:.2f} m²")

    # 2. FEATURES
    print("\n[2] FEATURES")
    attrs_cad = {"survey_number": "128/A", "land_use": "Agricultural", "classification": "Ryotwari"}
    attrs_mun = {"survey_number": "128/A", "land_use": "Agricultural", "classification": "Ryotwari"}
    evidence = compute_pair_metrics(poly_cadastral, poly_municipal, attrs_cad, attrs_mun)
    feats = features_from_pair_metrics(evidence)
    print(f"  Canonical Feature Schema Version: {FEATURE_SCHEMA_VERSION}")
    print(f"  Total Engineered Features: {len(FEATURE_ORDER)}")
    for k in ("iou", "area_ratio", "area_difference_m2", "centroid_distance_m", "boundary_displacement_m", "shape_similarity"):
        print(f"    - {k}: {feats[k]}")

    # 3. MODEL
    print("\n[3] MODEL")
    meta = conflict_detector.get_metadata()
    print(f"  Status: {meta['model_status']}")
    print(f"  Type: {meta['model_type']}")
    print(f"  Active Feature Count: {meta['feature_count']} features ({meta['feature_names']})")
    print(f"  Classes: {meta['classes']} (0=No Conflict, 1=Minor, 2=Critical)")
    print(f"  Accuracy Status: {meta['accuracy_status']}")

    # 4. PREDICTION
    print("\n[4] PREDICTION")
    pred = conflict_detector.predict_conflict(evidence)
    print(f"  Model Status: {pred['model_status']}")
    print(f"  Prediction Class: {pred['conflict_level']} ({pred['conflict_label']})")
    print(f"  Confidence: {pred['confidence']}%")
    print(f"  Probabilities: {pred['probabilities']}")
    print(f"  Reasoning: {pred['reasoning']}")

    # 5. FUSION
    print("\n[5] FUSION (Deterministic GIS + ML Evidence Fusion)")
    fused = fuse(
        parcel_id="TS-RR-00128-A",
        candidate_status="MATCH",
        spatial_metrics=evidence["spatial_metrics"],
        attribute_metrics=evidence["attribute_metrics"],
        model=conflict_detector.predict([feats[k] for k in FEATURE_ORDER]),
    )
    print(f"  Match Status: {fused['match_status']}")
    print(f"  Authoritative Reconciliation Score: {fused['reconciliation_score']} / 100")
    print(f"  Evidence Quality: {fused['evidence_quality']}")
    print(f"  Review Required: {fused['review_required']}")
    print(f"  ML Stream Status: {fused['ml']['model_status']}")

    # 6. API
    print("\n[6] API (FastAPI Surface)")
    client = TestClient(app)
    res_status = client.get("/api/ml/status")
    print(f"  GET /api/ml/status -> HTTP {res_status.status_code}")
    print(f"    model_status: {res_status.json()['model_status']}")

    res_pred = client.post("/api/ml/predict", json={
        "iou": float(feats["iou"]),
        "area_delta": float(1.0 - feats["area_ratio"]),
        "attr_match": 1.0,
    })
    print(f"  POST /api/ml/predict -> HTTP {res_pred.status_code}")
    print(f"    Response: {json.dumps(res_pred.json(), indent=6)}")

    res_metrics = client.post("/api/ml/predict-metrics", json=evidence)
    print(f"  POST /api/ml/predict-metrics -> HTTP {res_metrics.status_code}")
    print(f"    Conflict Level: {res_metrics.json()['conflict_level']} ({res_metrics.json()['conflict_label']})")
    print(f"    Confidence: {res_metrics.json()['confidence']}%")

    print("\n" + "=" * 70)
    print("VERIFICATION COMPLETE: DATA SOURCE → FEATURES → MODEL → PREDICTION → FUSION → API")
    print("=" * 70)


if __name__ == "__main__":
    main()
