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

from config import settings
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
            # Provenance: "sample" (synthetic) vs "upload" (user's real file)
            "cadastral_source": info.get("cadastral_source", "sample"),
            "municipal_source": info.get("municipal_source", "sample"),
            "cadastral_filename": info.get("cadastral_filename"),
            "municipal_filename": info.get("municipal_filename"),
            # Spec §6/§7: let the UI (and deployment checks) see the fixture
            # mode and whether the loaded data is synthetic.
            "demo_fixture_mode": settings.DEMO_FIXTURE_MODE,
            "data_state": (
                "SYNTHETIC_DEMO_DATA"
                if info.get("cadastral_source", "sample") != "upload"
                or info.get("municipal_source", "sample") != "upload"
                else "REAL_TO_REAL"
            ),
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
        "demo_fixture_mode": settings.DEMO_FIXTURE_MODE,
        # Explicit honest state: in production this is surfaced instead of
        # silently falling back to synthetic sample fixtures (spec §7).
        "data_state": "REAL_DATA_UNAVAILABLE",
    }
