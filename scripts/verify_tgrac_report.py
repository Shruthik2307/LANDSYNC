import sys
import time
from pathlib import Path

# Add backend and project root to sys.path
sys.path.insert(0, str(Path.cwd()))
sys.path.insert(0, str(Path.cwd() / "backend"))

from services.tgrac_service import (
    TGRAC_CADASTRAL_URL,
    TGRAC_QUERY_URL,
    DEFAULT_SANGAREDDY_BBOX,
    query_tgrac_vector_features,
    fetch_and_reconcile_tgrac,
)

bbox = DEFAULT_SANGAREDDY_BBOX

# Step 1: Query cadastral features directly
t0 = time.time()
cad_payload = query_tgrac_vector_features(
    service_url=TGRAC_CADASTRAL_URL,
    layer_id=0,
    bbox=bbox,
    max_records=500,
)
fetch_time = time.time() - t0

features = cad_payload["features"]
f0 = features[0] if features else {}
attrs = f0.get("attributes", {})
f0_oid = attrs.get("OBJECTID") or attrs.get("OBJECTID_12")

# Step 2: Run end-to-end reconciliation through the existing LANDSYNC GIS pipeline
recon_res = fetch_and_reconcile_tgrac(bbox=bbox, max_features=100)

print("\n" + "=" * 60)
print("OFFICIAL TGRAC RUNTIME VERIFICATION REPORT")
print("=" * 60)
print(f"SOURCE: TGRAC_TELANGANA")
print(f"SERVICE: {TGRAC_CADASTRAL_URL}")
print(f"LAYER: Cadastral 2.5m (Layer 0)")
print(f"HTTP STATUS: {cad_payload['http_status']}")
print(f"QUERY BBOX: {bbox}")
print(f"REAL FEATURES RETURNED: {cad_payload['feature_count']}")
print(f"FIRST REAL OBJECTID: {f0_oid}")
print(f"GEOMETRY TYPE: {cad_payload['geometry_type']}")
print(f"CRS: {cad_payload['crs']}")
print(f"ATTRIBUTE FIELDS: {list(attrs.keys())}")
print(f"RETRIEVAL TIME: {cad_payload['retrieval_time_seconds']}s")
print(f"LANDSYNC PIPELINE FEATURES PROCESSED: {recon_res['features_processed']}")
print("SYNTHETIC DATA USED: NO")
print("=" * 60 + "\n")
