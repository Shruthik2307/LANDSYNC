"""
backend/routes/model_info.py
============================
GET /api/model/info — honest ML model status and metrics (spec §21).

Reports MODEL_UNAVAILABLE with a reason when no validated artifact exists.
Never exposes secrets; never fabricates metrics that were not measured.
"""

from __future__ import annotations

from fastapi import APIRouter

from services.model_info import get_registry

router = APIRouter(tags=["model"])


@router.get("/api/model/info")
def model_info() -> dict:
    """Production model status, metrics, and feature contract."""
    return get_registry().info()
