"""
backend/routes/health.py
========================
GET /api/health — backend and engine status.

Response shape
--------------
{
    "status":          "ok" | "degraded",
    "service":         "landsync-backend",
    "version":         "1.0.0",
    "engine":          "loaded" | "unavailable",
    "parcel_count":    int,
    "cadastral_crs":   str,
    "municipal_crs":   str,
    "engine_crs":      "EPSG:3857",
}
"""

from __future__ import annotations

import logging

from fastapi import APIRouter

from services.landsync_service import (
    get_dataset_info,
    is_loaded,
)

logger = logging.getLogger(__name__)
router = APIRouter(tags=["health"])


@router.get("/api/health")
def health() -> dict:
    """Return backend status and engine/data-loading status.

    Always returns HTTP 200 — the `status` field indicates degradation.
    """
    if is_loaded():
        info = get_dataset_info()
        return {
            "status": "ok",
            "service": "landsync-backend",
            "version": "1.0.0",
            "engine": "loaded",
            "parcel_count": info.get("reconciled_parcel_count", 0),
            "cadastral_crs": info.get("cadastral_crs", "unknown"),
            "municipal_crs": info.get("municipal_crs", "unknown"),
            "engine_crs": info.get("engine_crs", "EPSG:3857"),
            "cadastral_features": info.get("cadastral_feature_count", 0),
            "municipal_features": info.get("municipal_feature_count", 0),
        }

    # Engine data not yet loaded
    return {
        "status": "degraded",
        "service": "landsync-backend",
        "version": "1.0.0",
        "engine": "unavailable",
        "detail": (
            "Parcel data has not been loaded. "
            "POST /api/process to trigger reconciliation."
        ),
    }
