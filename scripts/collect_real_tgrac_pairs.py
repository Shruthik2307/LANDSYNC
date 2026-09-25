"""
scripts/collect_real_tgrac_pairs.py
====================================
Collect genuine parcel comparison pairs from official TGRAC Telangana ArcGIS REST:
  - Cadastral Layer 0: Bhunaksha_Cadastral (Cadastral 2.5m, EPSG:4326)
  - Municipal Layer 1: Bhunaksha_query (ULB Cadastral 30cm, EPSG:4326)

Computes the canonical 14-feature spatial and attribute metrics for each overlapping pair.
Saves pairs to `data/unreviewed/tgrac_pairs.jsonl` awaiting expert human review.
Never assigns synthetic labels or fabricated ground truth.
"""
from __future__ import annotations

import json
import logging
import ssl
import sys
import time
import urllib.parse
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
backend_path = ROOT / "backend"
if str(backend_path) not in sys.path:
    sys.path.insert(0, str(backend_path))

import geopandas as gpd
from shapely.geometry import MultiPolygon, Polygon
from shapely.ops import unary_union
from shapely.validation import make_valid

from engine.metrics import compute_pair_metrics
from engine.ml_schema import FEATURE_ORDER, FEATURE_SCHEMA_VERSION, features_from_pair_metrics

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("tgrac_collector")

ctx = ssl._create_unverified_context()
headers = {"User-Agent": "Mozilla/5.0 (compatible; LANDSYNC/1.0; SIH26013)"}

TGRAC_CADASTRAL_URL = (
    "https://tgrac.telangana.gov.in/arcgis/rest/services/Bhunaksha_Folder/Bhunaksha_Cadastral/MapServer/0"
)
TGRAC_MUNICIPAL_URL = (
    "https://tgrac.telangana.gov.in/arcgis/rest/services/Bhunaksha_Folder/Bhunaksha_query/MapServer/1"
)

# Representative bounding boxes across Telangana
REGIONS = [
    {"name": "Sangareddy_Urban", "bbox": "78.06,17.60,78.08,17.62"},
    {"name": "Sangareddy_Suburban", "bbox": "78.08,17.60,78.10,17.62"},
]

OUTPUT_DIR = ROOT / "data" / "unreviewed"
OUTPUT_FILE = OUTPUT_DIR / "tgrac_pairs.jsonl"


def esri_rings_to_geometry(rings: list) -> Polygon | MultiPolygon | None:
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
        return MultiPolygon([p for p in polygons if p.geom_type == "Polygon"])


def fetch_layer(url: str, bbox: str, max_records: int = 100) -> gpd.GeoDataFrame:
    params = {
        "geometry": bbox,
        "geometryType": "esriGeometryEnvelope",
        "inSR": "4326",
        "spatialRel": "esriSpatialRelIntersects",
        "outSR": "4326",
        "outFields": "*",
        "returnGeometry": "true",
        "resultRecordCount": str(max_records),
        "f": "json",
    }
    full_url = f"{url}/query?{urllib.parse.urlencode(params)}"
    req = urllib.request.Request(full_url, headers=headers)
    with urllib.request.urlopen(req, context=ctx, timeout=30) as r:
        data = json.loads(r.read())

    features = data.get("features", [])
    records = []
    for f in features:
        attrs = dict(f.get("attributes", {}))
        rings = f.get("geometry", {}).get("rings", [])
        geom = esri_rings_to_geometry(rings)
        if geom is not None and not geom.is_empty:
            attrs["geometry"] = geom
            records.append(attrs)

    gdf = gpd.GeoDataFrame(records, crs="EPSG:4326")
    return gdf


def collect_pairs(limit_per_region: int = 50) -> list[dict]:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    all_pairs: list[dict] = []
    seen_pairs: set[str] = set()

    for region_info in REGIONS:
        r_name = region_info["name"]
        bbox = region_info["bbox"]
        logger.info("Fetching TGRAC features for %s (bbox=%s)...", r_name, bbox)

        try:
            gdf_cad = fetch_layer(TGRAC_CADASTRAL_URL, bbox, max_records=limit_per_region)
            gdf_mun = fetch_layer(TGRAC_MUNICIPAL_URL, bbox, max_records=limit_per_region)
        except Exception as exc:
            logger.error("Failed fetching TGRAC data for %s: %s", r_name, exc)
            continue

        logger.info("Fetched %d Cadastral and %d Municipal features.", len(gdf_cad), len(gdf_mun))
        if gdf_cad.empty or gdf_mun.empty:
            continue

        # Normalise IDs
        if "parcel_id" not in gdf_cad.columns:
            gdf_cad["parcel_id"] = gdf_cad.get("Parcel_num", gdf_cad["OBJECTID"]).astype(str).str.strip()
            gdf_cad.loc[gdf_cad["parcel_id"].isin(["", "nan", "None"]), "parcel_id"] = "CAD-" + gdf_cad["OBJECTID"].astype(str)

        if "parcel_id" not in gdf_mun.columns:
            gdf_mun["parcel_id"] = gdf_mun.get("Parcel_num", gdf_mun["OBJECTID"]).astype(str).str.strip()
            gdf_mun.loc[gdf_mun["parcel_id"].isin(["", "nan", "None"]), "parcel_id"] = "MUN-" + gdf_mun["OBJECTID"].astype(str)

        # Reproject to EPSG:3857 (metric) for rigorous GIS metrics
        gdf_cad_3857 = gdf_cad.to_crs(epsg=3857)
        gdf_mun_3857 = gdf_mun.to_crs(epsg=3857)

        # Spatial intersection join
        joined = gpd.sjoin(gdf_cad_3857, gdf_mun_3857, how="inner", predicate="intersects")
        logger.info("Found %d spatial intersections in %s.", len(joined), r_name)

        for _, row in joined.iterrows():
            cad_id = str(row.get("parcel_id_left", row.get("parcel_id", "CAD-UNKNOWN")))
            mun_id = str(row.get("parcel_id_right", row.get("parcel_id", "MUN-UNKNOWN")))
            pair_key = f"{cad_id}::{mun_id}"
            if pair_key in seen_pairs:
                continue
            seen_pairs.add(pair_key)

            geom_a = row.geometry
            # Look up municipal geometry from gdf_mun_3857
            idx_right = row.get("index_right")
            if idx_right not in gdf_mun_3857.index:
                continue
            geom_b = gdf_mun_3857.loc[idx_right].geometry

            if geom_a is None or geom_b is None or geom_a.is_empty or geom_b.is_empty:
                continue

            attrs_a = {k: v for k, v in row.items() if k.endswith("_left")}
            attrs_b = {k: v for k, v in gdf_mun_3857.loc[idx_right].items() if k != "geometry"}

            # Compute pure deterministic GIS evidence bundle
            evidence = compute_pair_metrics(geom_a, geom_b, attrs_a, attrs_b)
            canonical_features = features_from_pair_metrics(evidence)

            # Save geometries for visual review (both EPSG:4326 GeoJSON and metric)
            cad_geom_4326 = gdf_cad.loc[row.name].geometry if row.name in gdf_cad.index else None
            mun_geom_4326 = gdf_mun.loc[idx_right].geometry if idx_right in gdf_mun.index else None

            import shapely.geometry
            boundaries_4326 = {
                "cadastral": shapely.geometry.mapping(cad_geom_4326) if cad_geom_4326 is not None and not cad_geom_4326.is_empty else None,
                "municipal": shapely.geometry.mapping(mun_geom_4326) if mun_geom_4326 is not None and not mun_geom_4326.is_empty else None,
            }

            pair_record = {
                "pair_id": pair_key,
                "cadastral_id": cad_id,
                "municipal_id": mun_id,
                "region": r_name,
                "bbox": bbox,
                "collected_at": datetime.now(timezone.utc).isoformat(),
                "provenance": {
                    "source": "TGRAC_TELANGANA",
                    "cadastral_layer": "Bhunaksha_Cadastral Layer 0 (Cadastral 2.5m)",
                    "municipal_layer": "Bhunaksha_query Layer 1 (ULB Cadastral 30cm)",
                    "cadastral_url": TGRAC_CADASTRAL_URL,
                    "municipal_url": TGRAC_MUNICIPAL_URL,
                },
                "boundaries": boundaries_4326,
                "spatial_metrics": evidence["spatial_metrics"],
                "attribute_metrics": evidence["attribute_metrics"],
                "pair_metrics": evidence,
                "canonical_features": canonical_features,
            }
            all_pairs.append(pair_record)

    logger.info("Total unique TGRAC parcel pairs collected: %d", len(all_pairs))

    # Append to JSON Lines file
    with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
        for p in all_pairs:
            f.write(json.dumps(p) + "\n")

    logger.info("Saved %d pairs to %s", len(all_pairs), OUTPUT_FILE)
    return all_pairs


if __name__ == "__main__":
    collect_pairs(limit_per_region=50)
