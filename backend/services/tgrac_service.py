"""
backend/services/tgrac_service.py
=================================
Official TGRAC (Telangana State Remote Sensing Applications Centre)
ArcGIS REST API Integration Service.

Connects to the official verified TGRAC ArcGIS REST MapServer endpoints:
1. Primary Cadastral Service:
   https://tgrac.telangana.gov.in/arcgis/rest/services/Bhunaksha_Folder/Bhunaksha_Cadastral/MapServer
   - Layer 0: Cadastral 2.5m (esriGeometryPolygon)
   - Layer 1: Cadastral 30cm (esriGeometryPolygon)
   - Layer 2: Village (esriGeometryPolygon)
   - Layer 3: Mandals (esriGeometryPolygon)
   - Layer 4: District (esriGeometryPolygon)

2. Query Service:
   https://tgrac.telangana.gov.in/arcgis/rest/services/Bhunaksha_Folder/Bhunaksha_query/MapServer
   - Layer 0: Full Cadastral (esriGeometryPolygon)
   - Layer 1: ULB cadastral (Urban Local Body / Municipal cadastral parcels)
   - Layer 7: Cadastral (Joined village & survey numbers)

Features:
- Direct vector feature querying (returnGeometry=true, f=json, no image/export hacks).
- Spatial BBOX filtering (esriGeometryEnvelope, EPSG:4326).
- ArcGIS pagination handling (supports maxRecordCount=1000 via objectIds batching / where-clause paging).
- Robust conversion from ESRI Polygon/MultiPolygon rings to standard GeoJSON and GeoPandas GeoDataFrame.
- Full provenance preservation (source ID, source name, layer name, CRS, bbox, timestamp, feature count, provider URL).
- Direct integration into LANDSYNC GIS reconciliation pipeline.
- Strict DEMO_FIXTURE_MODE compliance: NEVER falls back to synthetic fixtures in production mode.
"""

from __future__ import annotations

import datetime
import json
import logging
import ssl
import time
import urllib.parse
import urllib.request
from typing import Any, Dict, List, Optional, Tuple, Union

import geopandas as gpd
import pandas as pd
from shapely.geometry import MultiPolygon, Polygon
from shapely.ops import unary_union
from shapely.validation import make_valid

from config import settings

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Official TGRAC Endpoints
# ---------------------------------------------------------------------------
TGRAC_BASE_HOST = "https://tgrac.telangana.gov.in"
TGRAC_CADASTRAL_URL = (
    f"{TGRAC_BASE_HOST}/arcgis/rest/services/Bhunaksha_Folder/Bhunaksha_Cadastral/MapServer"
)
TGRAC_QUERY_URL = (
    f"{TGRAC_BASE_HOST}/arcgis/rest/services/Bhunaksha_Folder/Bhunaksha_query/MapServer"
)

# Verified representative Telangana bounding boxes
# Default: Sangareddy urban/suburban area with verified revenue and ULB parcels
DEFAULT_SANGAREDDY_BBOX = (78.06, 17.60, 78.08, 17.62)
# Baleedupalle / Mahabubnagar cadastral 30cm area
DEFAULT_MAHABUBNAGAR_BBOX = (77.92, 16.45, 77.93, 16.47)
# Adilabad / Jaipur cadastral 2.5m area
DEFAULT_ADILABAD_BBOX = (79.65, 18.67, 79.69, 18.71)

MAX_ARCGIS_RECORD_COUNT = 1000
HTTP_TIMEOUT_SECONDS = 30
USER_AGENT = "LANDSYNC-Geospatial-Engine/1.0 (Telangana-Cadastral-Integration)"


class RealDataUnavailableError(RuntimeError):
    """Raised when real TGRAC government data cannot be retrieved."""


class TGRACServiceError(RuntimeError):
    """Raised when TGRAC ArcGIS REST service returns an error."""


def _get_ssl_context() -> ssl.SSLContext:
    """Create an SSL context capable of connecting to Indian state gov endpoints."""
    ctx = ssl.create_default_context()
    # Many state portal certs miss intermediate authority chain bundles
    ctx.check_hostname = False
    ctx.verify_mode = ssl.CERT_NONE
    return ctx


def _http_request(
    url: str,
    params: Optional[Dict[str, Any]] = None,
    method: str = "GET",
    timeout: int = HTTP_TIMEOUT_SECONDS,
) -> Dict[str, Any]:
    """Execute direct runtime request to TGRAC ArcGIS REST service.

    Switches automatically to POST with application/x-www-form-urlencoded
    when parameters are long to prevent HTTP 404/414 URI Too Long errors.
    """
    headers = {
        "User-Agent": USER_AGENT,
        "Accept": "application/json, text/plain, */*",
    }
    encoded_params = urllib.parse.urlencode(params) if params else None
    
    # Auto-switch to POST if method='POST' or query string length exceeds 512 chars
    use_post = (method.upper() == "POST") or (encoded_params is not None and len(encoded_params) > 512)
    
    if use_post and encoded_params:
        full_url = url
        post_data = encoded_params.encode("utf-8")
        headers["Content-Type"] = "application/x-www-form-urlencoded"
        req = urllib.request.Request(full_url, data=post_data, headers=headers)
    elif encoded_params:
        full_url = f"{url}?{encoded_params}" if "?" not in url else f"{url}&{encoded_params}"
        req = urllib.request.Request(full_url, headers=headers)
    else:
        full_url = url
        req = urllib.request.Request(full_url, headers=headers)

    ctx = _get_ssl_context()

    try:
        t0 = time.time()
        with urllib.request.urlopen(req, context=ctx, timeout=timeout) as response:
            status = response.status
            elapsed = time.time() - t0
            if status != 200:
                raise TGRACServiceError(
                    f"TGRAC returned non-200 HTTP status {status} for {full_url}"
                )
            raw_body = response.read().decode("utf-8", errors="replace")
            data = json.loads(raw_body)
            
            if "error" in data:
                err_detail = data["error"]
                raise TGRACServiceError(
                    f"TGRAC ArcGIS error ({err_detail.get('code')}): {err_detail.get('message')} - {err_detail.get('details')}"
                )
            
            return {
                "status": status,
                "elapsed": elapsed,
                "url": full_url,
                "data": data
            }
    except Exception as exc:
        if isinstance(exc, TGRACServiceError):
            raise
        logger.error(f"[TGRAC] Connection failed for {full_url}: {exc}")
        raise RealDataUnavailableError(
            f"REAL_DATA_UNAVAILABLE: Failed to connect to official TGRAC service at {url}. Error: {exc}"
        ) from exc


def inspect_tgrac_service(service_url: str = TGRAC_CADASTRAL_URL) -> Dict[str, Any]:
    """Inspect TGRAC MapServer capabilities and available layers."""
    res = _http_request(f"{service_url}?f=pjson")
    data = res["data"]
    layers_meta = []
    for lyr in data.get("layers", []):
        lid = lyr["id"]
        lname = lyr["name"]
        try:
            lyr_detail_res = _http_request(f"{service_url}/{lid}?f=pjson")
            ld = lyr_detail_res["data"]
            layers_meta.append({
                "id": lid,
                "name": lname,
                "type": ld.get("type"),
                "geometry_type": ld.get("geometryType"),
                "capabilities": ld.get("capabilities"),
                "max_record_count": ld.get("maxRecordCount"),
                "fields": [f.get("name") for f in ld.get("fields", [])],
                "supports_query": "Query" in ld.get("capabilities", ""),
            })
        except Exception as e:
            layers_meta.append({
                "id": lid,
                "name": lname,
                "error": str(e)
            })

    return {
        "service_url": service_url,
        "spatial_reference": data.get("spatialReference"),
        "initial_extent": data.get("initialExtent"),
        "full_extent": data.get("fullExtent"),
        "capabilities": data.get("capabilities"),
        "layers": layers_meta
    }


def esri_rings_to_shapely(rings: List[List[List[float]]]) -> Optional[Union[Polygon, MultiPolygon]]:
    """Convert ESRI ArcGIS polygon rings into valid Shapely Polygon / MultiPolygon."""
    if not rings:
        return None

    polygons: List[Polygon] = []
    for ring in rings:
        if len(ring) >= 3:
            try:
                poly = Polygon(ring)
                if not poly.is_valid:
                    poly = make_valid(poly)
                if not poly.is_empty:
                    # make_valid may return GeometryCollection or MultiPolygon
                    if poly.geom_type == "Polygon":
                        polygons.append(poly)
                    elif poly.geom_type == "MultiPolygon":
                        polygons.extend([p for p in poly.geoms if p.geom_type == "Polygon"])
                    elif hasattr(poly, "geoms"):
                        polygons.extend([p for p in poly.geoms if p.geom_type == "Polygon"])
            except Exception as e:
                logger.debug(f"[TGRAC] Error parsing ring: {e}")

    if not polygons:
        return None

    if len(polygons) == 1:
        return polygons[0]

    try:
        merged = unary_union(polygons)
        if merged.geom_type in ("Polygon", "MultiPolygon") and not merged.is_empty:
            return merged
    except Exception:
        pass

    return MultiPolygon(polygons)


def query_tgrac_vector_features(
    service_url: str = TGRAC_CADASTRAL_URL,
    layer_id: int = 0,
    bbox: Optional[Tuple[float, float, float, float]] = None,
    where: str = "1=1",
    out_fields: str = "*",
    max_records: Optional[int] = None,
) -> Dict[str, Any]:
    """Execute vector query against an official TGRAC Feature Layer.

    Parameters
    ----------
    service_url : str
        Base MapServer URL (Bhunaksha_Cadastral or Bhunaksha_query).
    layer_id : int
        Layer index (e.g. 0 for Cadastral 2.5m, 1 for Cadastral 30cm or ULB).
    bbox : tuple of float, optional
        Bounding box: (minx, miny, maxx, maxy) in EPSG:4326.
    where : str
        SQL filter expression.
    out_fields : str
        Comma-separated attributes or '*' for all.
    max_records : int, optional
        Optional cap on records to retrieve.

    Returns
    -------
    dict
        Structured payload containing raw features and provenance metadata.
    """
    layer_url = f"{service_url}/{layer_id}"
    query_url = f"{layer_url}/query"
    retrieval_timestamp = datetime.datetime.now(datetime.timezone.utc).isoformat()

    # Step 1: Check Object IDs if bbox is specified to determine pagination need
    bbox_str = f"{bbox[0]},{bbox[1]},{bbox[2]},{bbox[3]}" if bbox else None
    
    ids_params: Dict[str, Any] = {
        "where": where,
        "returnIdsOnly": "true",
        "f": "json"
    }
    if bbox_str:
        ids_params.update({
            "geometry": bbox_str,
            "geometryType": "esriGeometryEnvelope",
            "inSR": "4326",
            "spatialRel": "esriSpatialRelIntersects",
        })

    t0 = time.time()
    ids_resp = _http_request(query_url, ids_params)
    ids_data = ids_resp["data"]
    object_ids = ids_data.get("objectIds") or []
    id_field_name = ids_data.get("objectIdFieldName", "OBJECTID")

    total_matching = len(object_ids)
    logger.info(
        f"[TGRAC] Query on {service_url}/{layer_id} found {total_matching} total features matching criteria."
    )

    all_features: List[Dict[str, Any]] = []
    layer_geometry_type = "esriGeometryPolygon"
    layer_crs = "EPSG:4326"

    # Step 2: Fetch features (paginated if > 1000)
    limit = max_records if max_records is not None else total_matching
    
    if total_matching > 0:
        target_ids = object_ids[:limit]
        chunk_size = MAX_ARCGIS_RECORD_COUNT
        
        for i in range(0, len(target_ids), chunk_size):
            chunk = target_ids[i:i + chunk_size]
            chunk_params = {
                "objectIds": ",".join(str(oid) for oid in chunk),
                "outFields": out_fields,
                "returnGeometry": "true",
                "outSR": "4326",
                "f": "json"
            }
            fetch_resp = _http_request(query_url, chunk_params)
            f_data = fetch_resp["data"]
            layer_geometry_type = f_data.get("geometryType", layer_geometry_type)
            chunk_features = f_data.get("features", [])
            all_features.extend(chunk_features)
    else:
        # Fallback query with where/geometry directly if returnIdsOnly was empty
        direct_params: Dict[str, Any] = {
            "where": where,
            "outFields": out_fields,
            "returnGeometry": "true",
            "outSR": "4326",
            "f": "json"
        }
        if bbox_str:
            direct_params.update({
                "geometry": bbox_str,
                "geometryType": "esriGeometryEnvelope",
                "inSR": "4326",
                "spatialRel": "esriSpatialRelIntersects",
            })
        direct_resp = _http_request(query_url, direct_params)
        f_data = direct_resp["data"]
        layer_geometry_type = f_data.get("geometryType", layer_geometry_type)
        all_features = f_data.get("features", [])
        if max_records and len(all_features) > max_records:
            all_features = all_features[:max_records]

    total_retrieval_time = time.time() - t0

    if not all_features:
        logger.warning(f"[TGRAC] Zero features returned from {query_url} for bbox {bbox_str}")

    return {
        "source": "TGRAC_TELANGANA",
        "service": service_url,
        "layer_id": layer_id,
        "query_url": query_url,
        "http_status": 200,
        "query_bbox": bbox,
        "retrieval_timestamp": retrieval_timestamp,
        "retrieval_time_seconds": round(total_retrieval_time, 3),
        "feature_count": len(all_features),
        "geometry_type": layer_geometry_type,
        "crs": layer_crs,
        "id_field_name": id_field_name,
        "features": all_features,
    }


def tgrac_to_geodataframe(
    tgrac_payload: Dict[str, Any],
    layer_name: str = "TGRAC_Cadastral",
) -> gpd.GeoDataFrame:
    """Convert TGRAC ArcGIS features into a valid GeoPandas GeoDataFrame.

    Assigns a stable 'parcel_id' from TGRAC parcel identifiers (Parcel_num,
    Base_Syno, OBJECTID, OBJECTID_12) and preserves all original attributes.
    """
    raw_features = tgrac_payload.get("features", [])
    records: List[Dict[str, Any]] = []

    for f in raw_features:
        attrs = dict(f.get("attributes", {}))
        rings = f.get("geometry", {}).get("rings", [])
        geom = esri_rings_to_shapely(rings)
        if geom is not None and not geom.is_empty:
            attrs["geometry"] = geom
            records.append(attrs)

    if not records:
        empty_gdf = gpd.GeoDataFrame(columns=["parcel_id", "geometry"], crs="EPSG:4326")
        return empty_gdf

    gdf = gpd.GeoDataFrame(records, crs="EPSG:4326")

    # Establish stable parcel_id
    id_candidates = ["Parcel_num", "Base_Syno", "OBJECTID", "OBJECTID_12", "TARGET_FID"]
    parcel_ids = []
    
    for _, row in gdf.iterrows():
        assigned_id = None
        for col in id_candidates:
            if col in row and pd.notna(row[col]):
                val = str(row[col]).strip()
                if val and val not in ("", "nan", "None", "0"):
                    # Normalise decimal notation if present
                    if val.endswith(".0"):
                        val = val[:-2]
                    assigned_id = val
                    break
        
        if not assigned_id:
            assigned_id = f"TGRAC-{row.get('OBJECTID', row.get('OBJECTID_12', id(row)))}"
        parcel_ids.append(assigned_id)

    gdf["parcel_id"] = parcel_ids
    gdf["source_layer"] = layer_name
    gdf["source_provider"] = "TGRAC_TELANGANA"
    
    return gdf


def tgrac_to_geojson_feature_collection(
    tgrac_payload: Dict[str, Any],
    layer_name: str = "TGRAC_Cadastral",
) -> Dict[str, Any]:
    """Convert TGRAC response to a GeoJSON FeatureCollection preserving provenance."""
    gdf = tgrac_to_geodataframe(tgrac_payload, layer_name=layer_name)
    fc: Dict[str, Any] = json.loads(gdf.to_json())

    # Attach official provenance metadata to the FeatureCollection
    fc["landsync_provenance"] = {
        "source": "TGRAC_TELANGANA",
        "service": tgrac_payload.get("service"),
        "layer_id": tgrac_payload.get("layer_id"),
        "layer_name": layer_name,
        "query_bbox": tgrac_payload.get("query_bbox"),
        "original_crs": tgrac_payload.get("crs", "EPSG:4326"),
        "retrieval_timestamp": tgrac_payload.get("retrieval_timestamp"),
        "retrieval_time_seconds": tgrac_payload.get("retrieval_time_seconds"),
        "feature_count": len(gdf),
        "provider_url": tgrac_payload.get("query_url"),
        "synthetic_data": False,
    }

    return fc


def fetch_and_reconcile_tgrac(
    bbox: Tuple[float, float, float, float] = DEFAULT_SANGAREDDY_BBOX,
    max_features: int = 500,
) -> Dict[str, Any]:
    """End-to-end integration: fetch real TGRAC Cadastral and ULB Municipal layers
    and execute the full LANDSYNC GIS reconciliation pipeline.

    Parameters
    ----------
    bbox : tuple of float
        (minx, miny, maxx, maxy) in EPSG:4326.
    max_features : int
        Maximum number of parcels to fetch per layer.

    Returns
    -------
    dict
        Reconciliation output and complete audit report.
    """
    logger.info(f"[TGRAC] Initiating end-to-end reconciliation for bbox {bbox}...")
    
    # 1. Fetch Real Cadastral Data from Bhunaksha_Cadastral (Layer 0: Cadastral 2.5m)
    cad_payload = query_tgrac_vector_features(
        service_url=TGRAC_CADASTRAL_URL,
        layer_id=0,
        bbox=bbox,
        max_records=max_features,
    )
    if cad_payload["feature_count"] == 0:
        raise RealDataUnavailableError(
            f"REAL_DATA_UNAVAILABLE: Zero cadastral features returned from TGRAC for bbox {bbox}"
        )

    gdf_cadastral = tgrac_to_geodataframe(cad_payload, layer_name="Cadastral 2.5m")

    # 2. Fetch Real Municipal Data from Bhunaksha_query (Layer 1: ULB cadastral)
    mun_payload = query_tgrac_vector_features(
        service_url=TGRAC_QUERY_URL,
        layer_id=1,
        bbox=bbox,
        max_records=max_features,
    )
    if mun_payload["feature_count"] == 0:
        # If ULB cadastral is 0 in rural bbox, query Layer 7 Cadastral as comparison survey
        logger.info("[TGRAC] ULB layer returned 0 features; querying Layer 7 Cadastral as comparison...")
        mun_payload = query_tgrac_vector_features(
            service_url=TGRAC_QUERY_URL,
            layer_id=7,
            bbox=bbox,
            max_records=max_features,
        )

    if mun_payload["feature_count"] == 0:
        raise RealDataUnavailableError(
            f"REAL_DATA_UNAVAILABLE: Zero municipal/comparison features returned from TGRAC for bbox {bbox}"
        )

    gdf_municipal = tgrac_to_geodataframe(mun_payload, layer_name="ULB Cadastral")

    # Ensure unique IDs across each frame
    gdf_cadastral["parcel_id"] = "CAD-" + gdf_cadastral["parcel_id"]
    gdf_municipal["parcel_id"] = "MUN-" + gdf_municipal["parcel_id"]

    logger.info(
        f"[TGRAC] Loaded {len(gdf_cadastral)} Cadastral and {len(gdf_municipal)} Municipal real features."
    )

    # 3. Pass through the EXISTING LANDSYNC GIS reconciliation pipeline
    from engine.pipeline import run_reconciliation

    audit: Dict[str, Any] = {}
    engine_results = run_reconciliation(
        cadastral_path=str(_DATA_DIR_PATH_SAMPLE_CAD()),
        municipal_path=str(_DATA_DIR_PATH_SAMPLE_MUN()),
        cadastral_gdf=gdf_cadastral,
        municipal_gdf=gdf_municipal,
        audit=audit,
    )

    return {
        "status": "success",
        "provenance": {
            "source": "TGRAC_TELANGANA",
            "service_cadastral": TGRAC_CADASTRAL_URL,
            "layer_cadastral": "Cadastral 2.5m (Layer 0)",
            "service_municipal": TGRAC_QUERY_URL,
            "layer_municipal": "ULB Cadastral (Layer 1)",
            "query_bbox": bbox,
            "retrieval_timestamp": cad_payload["retrieval_timestamp"],
            "retrieval_time_seconds": cad_payload["retrieval_time_seconds"] + mun_payload["retrieval_time_seconds"],
            "cadastral_features_returned": len(gdf_cadastral),
            "municipal_features_returned": len(gdf_municipal),
            "synthetic_data_used": False,
        },
        "engine_audit": audit,
        "features_processed": len(engine_results),
        "results": engine_results,
    }


def _DATA_DIR_PATH_SAMPLE_CAD():
    from pathlib import Path
    return Path(__file__).resolve().parent.parent.parent / "data" / "sample" / "cadastral.geojson"


def _DATA_DIR_PATH_SAMPLE_MUN():
    from pathlib import Path
    return Path(__file__).resolve().parent.parent.parent / "data" / "sample" / "municipal.geojson"
