"""
backend/routes/tgrac.py
=======================
API routes for querying and reconciling official TGRAC (Telangana State Remote
Sensing Applications Centre) cadastral and municipal GIS data.

Endpoints:
- GET  /api/tgrac/status  — Verify official TGRAC service connectivity & capabilities.
- GET  /api/tgrac/layers  — List queryable vector feature layers from both TGRAC MapServers.
- POST /api/tgrac/query   — Query real vector features for a Telangana bounding box as GeoJSON.
- POST /api/tgrac/load    — Fetch real TGRAC cadastral data, run reconciliation, and populate cache.
"""

from __future__ import annotations

import logging
from typing import Any, Dict, List, Literal, Optional, Tuple

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel, Field

from config import settings
from services.landsync_service import load_tgrac_data
from services.tgrac_service import (
    DEFAULT_SANGAREDDY_BBOX,
    TGRAC_CADASTRAL_URL,
    TGRAC_QUERY_URL,
    RealDataUnavailableError,
    TGRACServiceError,
    inspect_tgrac_service,
    query_tgrac_vector_features,
    tgrac_to_geojson_feature_collection,
)

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/tgrac", tags=["tgrac"])


class TGRACQueryRequest(BaseModel):
    service: Literal["Bhunaksha_Cadastral", "Bhunaksha_query"] = Field(
        default="Bhunaksha_Cadastral",
        description="Target TGRAC MapServer service name",
    )
    layer_id: int = Field(default=0, ge=0, le=10, description="Layer index to query")
    bbox: Optional[Tuple[float, float, float, float]] = Field(
        default=DEFAULT_SANGAREDDY_BBOX,
        description="Bounding box (minx, miny, maxx, maxy) in EPSG:4326",
    )
    max_records: Optional[int] = Field(
        default=100,
        ge=1,
        le=1000,
        description="Maximum number of features to return",
    )


class TGRACLoadRequest(BaseModel):
    bbox: Optional[Tuple[float, float, float, float]] = Field(
        default=DEFAULT_SANGAREDDY_BBOX,
        description="Bounding box (minx, miny, maxx, maxy) in EPSG:4326",
    )
    max_features: int = Field(
        default=500,
        ge=1,
        le=1000,
        description="Max features per layer to ingest",
    )


@router.get("/status")
def tgrac_status() -> Dict[str, Any]:
    """Verify live connectivity and capabilities of official TGRAC ArcGIS REST services.

    Queries both Bhunaksha_Cadastral and Bhunaksha_query services at runtime.
    """
    logger.info("[TGRAC] Checking official TGRAC service status...")
    results: Dict[str, Any] = {
        "provider": "Telangana State Remote Sensing Applications Centre (TGRAC)",
        "host": "tgrac.telangana.gov.in",
        "demo_fixture_mode": settings.DEMO_FIXTURE_MODE,
        "services": {},
    }

    # 1. Bhunaksha_Cadastral
    try:
        cad_info = inspect_tgrac_service(TGRAC_CADASTRAL_URL)
        results["services"]["Bhunaksha_Cadastral"] = {
            "status": "ONLINE",
            "url": TGRAC_CADASTRAL_URL,
            "crs": cad_info.get("spatial_reference"),
            "layer_count": len(cad_info.get("layers", [])),
            "layers": [
                {
                    "id": lyr["id"],
                    "name": lyr["name"],
                    "geometry_type": lyr.get("geometry_type"),
                    "capabilities": lyr.get("capabilities"),
                }
                for lyr in cad_info.get("layers", [])
            ],
        }
    except Exception as exc:
        logger.error(f"[TGRAC] Bhunaksha_Cadastral check failed: {exc}")
        results["services"]["Bhunaksha_Cadastral"] = {
            "status": "OFFLINE",
            "url": TGRAC_CADASTRAL_URL,
            "error": str(exc),
        }

    # 2. Bhunaksha_query
    try:
        qry_info = inspect_tgrac_service(TGRAC_QUERY_URL)
        results["services"]["Bhunaksha_query"] = {
            "status": "ONLINE",
            "url": TGRAC_QUERY_URL,
            "crs": qry_info.get("spatial_reference"),
            "layer_count": len(qry_info.get("layers", [])),
            "layers": [
                {
                    "id": lyr["id"],
                    "name": lyr["name"],
                    "geometry_type": lyr.get("geometry_type"),
                    "capabilities": lyr.get("capabilities"),
                }
                for lyr in qry_info.get("layers", [])
            ],
        }
    except Exception as exc:
        logger.error(f"[TGRAC] Bhunaksha_query check failed: {exc}")
        results["services"]["Bhunaksha_query"] = {
            "status": "OFFLINE",
            "url": TGRAC_QUERY_URL,
            "error": str(exc),
        }

    online_count = sum(
        1 for s in results["services"].values() if s.get("status") == "ONLINE"
    )
    results["overall_status"] = "OK" if online_count > 0 else "UNAVAILABLE"

    return results


@router.get("/layers")
def list_tgrac_layers() -> Dict[str, Any]:
    """List all available official TGRAC Feature Layers and their attributes."""
    try:
        cad_info = inspect_tgrac_service(TGRAC_CADASTRAL_URL)
        qry_info = inspect_tgrac_service(TGRAC_QUERY_URL)
        return {
            "Bhunaksha_Cadastral": cad_info.get("layers", []),
            "Bhunaksha_query": qry_info.get("layers", []),
        }
    except Exception as exc:
        raise HTTPException(
            status_code=503,
            detail=f"REAL_DATA_UNAVAILABLE: Failed to inspect TGRAC layers: {exc}",
        )


@router.post("/query")
def query_features(request: TGRACQueryRequest) -> Dict[str, Any]:
    """Query real vector features from a TGRAC layer for a bounding box.

    Returns a GeoJSON FeatureCollection with original attributes, geometries,
    and landsync_provenance metadata.
    """
    service_url = (
        TGRAC_CADASTRAL_URL
        if request.service == "Bhunaksha_Cadastral"
        else TGRAC_QUERY_URL
    )
    try:
        raw_payload = query_tgrac_vector_features(
            service_url=service_url,
            layer_id=request.layer_id,
            bbox=request.bbox,
            max_records=request.max_records,
        )
        geojson = tgrac_to_geojson_feature_collection(
            raw_payload,
            layer_name=f"{request.service}_Layer{request.layer_id}",
        )
        return geojson
    except RealDataUnavailableError as exc:
        raise HTTPException(status_code=503, detail=str(exc))
    except Exception as exc:
        logger.exception("[TGRAC] Query failed")
        raise HTTPException(
            status_code=500,
            detail=f"Failed to query TGRAC features: {exc}",
        )


@router.post("/load")
def load_tgrac_dataset(request: TGRACLoadRequest) -> Dict[str, Any]:
    """Fetch real TGRAC Cadastral and ULB Municipal data, run reconciliation,
    and store the results in the LANDSYNC service cache.

    Subsequent calls to /api/parcels and /api/conflicts will serve this real data.
    """
    try:
        info = load_tgrac_data(
            bbox=request.bbox or DEFAULT_SANGAREDDY_BBOX,
            max_features=request.max_features,
            force_reload=True,
        )
        return {
            "job_status": "complete",
            "message": "Real TGRAC government data reconciled and loaded successfully.",
            "reconciled_parcel_count": info.get("reconciled_parcel_count", 0),
            "provenance": info.get("tgrac_provenance", {}),
        }
    except RealDataUnavailableError as exc:
        raise HTTPException(status_code=503, detail=str(exc))
    except Exception as exc:
        logger.exception("[TGRAC] Load failed")
        raise HTTPException(
            status_code=500,
            detail=f"Failed to load real TGRAC data: {exc}",
        )
