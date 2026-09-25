import urllib.request
import urllib.parse
import ssl
import json
import time
from shapely.geometry import Polygon, MultiPolygon
from shapely.validation import make_valid
from shapely.ops import unary_union
import geopandas as gpd
import pandas as pd
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from engine.pipeline import run_reconciliation

ctx = ssl._create_unverified_context()
headers = {'User-Agent': 'Mozilla/5.0 LANDSYNC/1.0'}

def esri_rings_to_geometry(rings):
    if not rings:
        return None
    polygons = []
    for ring in rings:
        if len(ring) >= 3:
            try:
                p = Polygon(ring)
                if not p.is_valid:
                    p = make_valid(p)
                if not p.is_empty:
                    polygons.append(p)
            except Exception:
                pass
    if not polygons:
        return None
    if len(polygons) == 1:
        return polygons[0]
    try:
        return unary_union(polygons)
    except Exception:
        return MultiPolygon([p for p in polygons if p.geom_type == 'Polygon'])

def fetch_layer(url, bbox, max_records=50):
    params = {
        "geometry": bbox,
        "geometryType": "esriGeometryEnvelope",
        "inSR": "4326",
        "spatialRel": "esriSpatialRelIntersects",
        "outSR": "4326",
        "outFields": "*",
        "returnGeometry": "true",
        "resultRecordCount": str(max_records),
        "f": "json"
    }
    full_url = f"{url}/query?{urllib.parse.urlencode(params)}"
    req = urllib.request.Request(full_url, headers=headers)
    t0 = time.time()
    with urllib.request.urlopen(req, context=ctx, timeout=30) as r:
        elapsed = time.time() - t0
        data = json.loads(r.read())
    
    features = data.get("features", [])
    records = []
    for f in features:
        attrs = dict(f.get("attributes", {}))
        rings = f.get("geometry", {}).get("rings", [])
        geom = esri_rings_to_geometry(rings)
        if geom:
            attrs["geometry"] = geom
            records.append(attrs)
    
    gdf = gpd.GeoDataFrame(records, crs="EPSG:4326")
    return gdf, elapsed, full_url

bbox = "78.06,17.60,78.08,17.62"

print("Fetching Cadastral (Revenue) Layer...")
url_cad = "https://tgrac.telangana.gov.in/arcgis/rest/services/Bhunaksha_Folder/Bhunaksha_Cadastral/MapServer/0"
gdf_cad, elapsed_cad, full_url_cad = fetch_layer(url_cad, bbox, max_records=50)
print(f"Cadastral fetched: {len(gdf_cad)} features in {elapsed_cad:.2f}s")

print("Fetching Municipal (ULB) Layer...")
url_mun = "https://tgrac.telangana.gov.in/arcgis/rest/services/Bhunaksha_Folder/Bhunaksha_query/MapServer/1"
gdf_mun, elapsed_mun, full_url_mun = fetch_layer(url_mun, bbox, max_records=50)
print(f"Municipal fetched: {len(gdf_mun)} features in {elapsed_mun:.2f}s")

# Add parcel_id if needed
if "parcel_id" not in gdf_cad.columns:
    # Use Parcel_num or OBJECTID
    gdf_cad["parcel_id"] = gdf_cad["Parcel_num"].astype(str).str.strip()
    gdf_cad.loc[gdf_cad["parcel_id"].isin(["", "nan", "None"]), "parcel_id"] = "CAD-" + gdf_cad["OBJECTID"].astype(str)

if "parcel_id" not in gdf_mun.columns:
    gdf_mun["parcel_id"] = gdf_mun["Parcel_num"].astype(str).str.strip()
    gdf_mun.loc[gdf_mun["parcel_id"].isin(["", "nan", "None"]), "parcel_id"] = "MUN-" + gdf_mun["OBJECTID"].astype(str)

print("Running LANDSYNC GIS Reconciliation Pipeline...")
# Pass temporary dummy paths for existence checks or pass mock paths
audit = {}
results = run_reconciliation(
    cadastral_path="data/sample/cadastral.geojson",
    municipal_path="data/sample/municipal.geojson",
    cadastral_gdf=gdf_cad,
    municipal_gdf=gdf_mun,
    audit=audit
)

print(f"Reconciliation completed successfully!")
print(f"Total features processed: {len(results)}")
print(f"First result parcel_id: {results[0]['parcel_id']}")
print(f"First result confidence: {results[0]['confidence']}")
print(f"First result priority: {results[0]['priority']}")
print(f"First result geometry_conflict: {results[0]['geometry_conflict']}")
print(f"First result match_status: {results[0]['match_status']}")
