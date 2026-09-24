"""
GET /api/imagery/info — REAL imagery provenance for a location.
================================================================

Returns what the selected imagery actually is: provider, acquisition date
when the provider publishes one, native resolution, and honest suitability
notes. Dates come from Esri's Wayback metadata service (real source-image
records) — when a date cannot be determined the response says so
("Imagery acquisition date unavailable") and never fabricates one.
"""
from __future__ import annotations

import logging

from fastapi import APIRouter, Query

from services.imagery_provenance import (
    get_esri_imagery_info,
    get_provider_catalog,
    get_sentinel2_info,
)

logger = logging.getLogger(__name__)

router = APIRouter()


@router.get("/api/imagery/info")
async def imagery_info(
    lng: float = Query(..., ge=-180, le=180, description="Longitude (WGS84)"),
    lat: float = Query(..., ge=-90, le=90, description="Latitude (WGS84)"),
    source: str = Query("esri_wayback", description="Imagery provider id"),
) -> dict:
    """Provenance of the observation imagery covering (lng, lat)."""
    if source == "sentinel2":
        info = await get_sentinel2_info(lng, lat)
    else:
        # Default: the Esri World Imagery mosaic the basemap actually shows.
        info = await get_esri_imagery_info(lng, lat)

    return {
        "status": "ok",
        "imagery": {
            **info,
            "label": "LATEST AVAILABLE IMAGERY",
            "real_time": False,
            "disclaimer": (
                "Mosaic of satellite and aerial images from different dates. "
                "Not a live or real-time view."
            ),
        },
        "providers": get_provider_catalog(),
    }
