"""
backend/routes/parcels.py
=========================
GET /api/parcels        — list all 25 reconciled parcels.
GET /api/parcels/{id}   — get a single parcel by parcel_id.

Response shape (matches OpenAPI Parcel schema + frontend src/api.js):
    {
        parcel_id         : str,
        confidence        : int (0–100),
        priority          : "HIGH" | "MEDIUM" | "LOW",
        area_difference   : float  (signed m², EPSG:3857),
        geometry_conflict : bool,
        attribute_conflict: bool,
        duplicate_id      : bool,
        recommendation    : str,
        boundaries        : {
            cadastral : GeoJSONPolygon,
            drone_ori : GeoJSONPolygon   (present only when geometry_conflict == True)
        }
    }

Auto-load
---------
If the cache is empty when GET /api/parcels is called, the service will
attempt to load and reconcile the sample data automatically. This means
the frontend works without requiring a prior POST /api/process call.
"""

from __future__ import annotations

import logging

from fastapi import APIRouter, HTTPException

from config import settings
from services.landsync_service import (
    DataNotReadyError,
    ParcelNotFoundError,
    get_all_parcels,
    get_parcel_by_id,
    is_loaded,
    load_data,
)

logger = logging.getLogger(__name__)
router = APIRouter(tags=["parcels"])


def _ensure_loaded() -> None:
    """Auto-load sample data ONLY in demo mode — never silently in production.

    In DEMO_FIXTURE_MODE=true (development / CI / offline demos), GET /api/parcels
    may auto-load the synthetic sample so the first call works without a prior
    POST /api/process. In production (DEMO_FIXTURE_MODE=false) the backend never
    substitutes synthetic data: when no real dataset has been uploaded/processed,
    the API reports an explicit REAL_DATA_UNAVAILABLE state instead.
    """
    if is_loaded():
        return
    if not settings.DEMO_FIXTURE_MODE:
        raise HTTPException(
            status_code=503,
            detail=(
                "REAL_DATA_UNAVAILABLE: no real dataset has been uploaded and "
                "processed yet. Upload real cadastral and municipal data via "
                "POST /api/upload, then run POST /api/process. Synthetic demo "
                "fixtures are disabled in production (DEMO_FIXTURE_MODE=false)."
            ),
        )
    logger.info("[parcels] Cache empty — DEMO_FIXTURE_MODE: auto-loading synthetic sample data.")
    try:
        load_data()
    except FileNotFoundError as exc:
        raise HTTPException(
            status_code=500,
            detail=f"Sample GeoJSON not found: {exc}",
        )
    except ValueError as exc:
        raise HTTPException(
            status_code=500,
            detail=f"Invalid GeoJSON data: {exc}",
        )
    except Exception as exc:  # pragma: no cover
        logger.exception("[parcels] Auto-load failed")
        raise HTTPException(
            status_code=500,
            detail=f"Failed to load parcel data: {exc}",
        )


@router.get("/api/parcels")
def list_parcels() -> list:
    """Return all reconciled parcels.

    In demo mode this auto-loads the synthetic sample when the cache is empty;
    in production it reports REAL_DATA_UNAVAILABLE until a real dataset has
    been uploaded and processed. Returns an empty list if no parcels could be
    reconciled.
    """
    _ensure_loaded()
    try:
        return get_all_parcels()
    except DataNotReadyError:  # pragma: no cover
        return []


@router.get("/api/parcels/{parcel_id}")
def get_parcel(parcel_id: str) -> dict:
    """Return a single parcel by parcel_id.

    Parameters
    ----------
    parcel_id : str
        The parcel identifier, e.g. ``HYD-REV-1000``.

    Raises
    ------
    404
        If the parcel_id does not exist in the reconciled dataset.
    """
    _ensure_loaded()
    try:
        return get_parcel_by_id(parcel_id)
    except ParcelNotFoundError:
        raise HTTPException(
            status_code=404,
            detail=f"Parcel not found: {parcel_id!r}",
        )
    except DataNotReadyError:  # pragma: no cover
        raise HTTPException(
            status_code=503,
            detail="Parcel data is not yet available. POST /api/process first.",
        )
