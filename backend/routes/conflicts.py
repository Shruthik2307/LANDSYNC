"""
backend/routes/conflicts.py
===========================
GET /api/conflicts — return only parcels that have conflicts, sorted by
priority (HIGH first) then confidence (descending).

A parcel is a conflict if ANY of:
    - geometry_conflict  == True
    - attribute_conflict == True
    - duplicate_id       == True

This matches the mock server logic in server/mock-server.mjs and the
frontend api.js getConflicts() consumer.

Sorting mirrors the mock server:
    priorityOrder = { HIGH: 3, MEDIUM: 2, LOW: 1 }
    sort by priority desc, then confidence desc
"""

from __future__ import annotations

import logging

from fastapi import APIRouter, HTTPException

from config import settings
from services.landsync_service import (
    DataNotReadyError,
    get_conflicts,
    is_loaded,
    load_data,
)

logger = logging.getLogger(__name__)
router = APIRouter(tags=["conflicts"])


def _ensure_loaded() -> None:
    """Auto-load sample data ONLY in demo mode — never silently in production.

    Mirrors routes/parcels.py: with DEMO_FIXTURE_MODE=false an empty cache
    surfaces an explicit REAL_DATA_UNAVAILABLE state instead of loading the
    synthetic sample fixtures.
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
    logger.info("[conflicts] Cache empty — DEMO_FIXTURE_MODE: auto-loading synthetic sample data.")
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
        logger.exception("[conflicts] Auto-load failed")
        raise HTTPException(
            status_code=500,
            detail=f"Failed to load conflict data: {exc}",
        )


@router.get("/api/conflicts")
def list_conflicts() -> list:
    """Return conflict parcels sorted by priority then confidence.

    Triggers automatic loading from sample data if the cache is empty.
    Returns an empty list if no conflicts are detected.
    """
    _ensure_loaded()
    try:
        return get_conflicts()
    except DataNotReadyError:  # pragma: no cover
        return []
