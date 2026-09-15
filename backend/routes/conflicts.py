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

from services.landsync_service import (
    DataNotReadyError,
    get_conflicts,
    is_loaded,
    load_data,
)

logger = logging.getLogger(__name__)
router = APIRouter(tags=["conflicts"])


def _ensure_loaded() -> None:
    """Auto-load sample data if the cache is empty."""
    if not is_loaded():
        logger.info("[conflicts] Cache empty — auto-loading sample data.")
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
