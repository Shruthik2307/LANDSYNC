"""
backend/routes/process.py
=========================
POST /api/process — trigger the LANDSYNC engine reconciliation pipeline.

Phase 1 behaviour
-----------------
• Accepts { dataset_id: str } (OpenAPI contract: ProcessRequest).
• Calls services.landsync_service.load_data() which runs:
      engine.pipeline.run_reconciliation(cadastral.geojson, municipal.geojson)
• Returns { job_status: "complete" } on success (OpenAPI: ProcessResponse).
• Returns { job_status: "failed" } with error detail on engine errors.

Note: For Phase 1 the dataset_id is accepted but not used to select a
different data file — reconciliation always runs on the two sample GeoJSON
files. This interface is intentionally kept compatible with the future
multi-source upload workflow.
"""

from __future__ import annotations

import logging
from typing import Literal

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from services.landsync_service import (
    DataNotReadyError,
    load_data,
)

logger = logging.getLogger(__name__)
router = APIRouter(tags=["process"])


class ProcessRequest(BaseModel):
    """Matches OpenAPI ProcessRequest schema."""
    dataset_id: str


class ProcessResponse(BaseModel):
    """Matches OpenAPI ProcessResponse schema."""
    job_status: Literal["queued", "processing", "complete", "failed"]


@router.post("/api/process", response_model=ProcessResponse)
def process_dataset(request: ProcessRequest) -> ProcessResponse:
    """Run the LANDSYNC reconciliation engine.

    Loads cadastral + municipal GeoJSON, runs the engine pipeline, and
    caches the results. Subsequent GET /api/parcels and GET /api/conflicts
    calls will return the reconciled data.

    Parameters
    ----------
    request.dataset_id : str
        ID returned by POST /api/upload. Currently used as a signal to
        trigger processing; Phase 1 always reconciles the sample dataset.
    """
    logger.info("[process] Received process request for dataset_id=%r", request.dataset_id)

    try:
        info = load_data(force_reload=True)
        parcel_count = info.get("reconciled_parcel_count", 0)
        logger.info(
            "[process] Reconciliation complete: %d parcels produced.", parcel_count
        )
        return ProcessResponse(job_status="complete")

    except FileNotFoundError as exc:
        logger.error("[process] Data file missing: %s", exc)
        raise HTTPException(
            status_code=500,
            detail=f"Engine data file not found: {exc}",
        )

    except ValueError as exc:
        logger.error("[process] GeoJSON validation error: %s", exc)
        raise HTTPException(
            status_code=422,
            detail=f"Invalid GeoJSON data: {exc}",
        )

    except Exception as exc:  # pragma: no cover
        logger.exception("[process] Unexpected engine error")
        raise HTTPException(
            status_code=500,
            detail=f"Engine processing failed: {exc}",
        )
