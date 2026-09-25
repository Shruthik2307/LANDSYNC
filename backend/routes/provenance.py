"""
backend/routes/provenance.py
============================
GET /api/data/provenance — full provenance for the loaded datasets
(spec §4): sources, CRS, retrieval facts, real/synthetic classification,
normalisation audit, and match-status distribution.

GET /api/reconciliation/{parcel_id} — full structured evidence for one
parcel (spec §18/§20): raw spatial metrics, attribute agreement, imagery
block, ML stream, and fusion assessment.
"""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, HTTPException

from services.landsync_service import (
    DataNotReadyError,
    ParcelNotFoundError,
    get_dataset_info,
    is_loaded,
)

router = APIRouter(tags=["provenance"])


@router.get("/api/data/provenance")
def data_provenance() -> dict:
    """Provenance for every dataset currently loaded in the engine."""
    if not is_loaded():
        return {
            "status": "REAL_DATA_NOT_AVAILABLE",
            "detail": "No dataset has been loaded. Upload real data via POST /api/upload.",
            "datasets": [],
        }
    info = get_dataset_info()
    cad_src = info.get("cadastral_source", "SYNTHETIC_DEMO")
    mun_src = info.get("municipal_source", "SYNTHETIC_DEMO")

    if cad_src == "USER_UPLOADED_REAL" and mun_src == "USER_UPLOADED_REAL":
        classification = "REAL_DATA"
        reconciliation_mode = "REAL → REAL RECONCILIATION"
    elif cad_src == "USER_UPLOADED_REAL" or mun_src == "USER_UPLOADED_REAL":
        classification = "REAL + SAMPLE MIXED"
        reconciliation_mode = "REAL vs SYNTHETIC (warning: not like-for-like)"
    else:
        classification = "SYNTHETIC_DEMO_DATA"
        reconciliation_mode = "SYNTHETIC DEMONSTRATION"

    def _dataset(side: str, src: str, filename: Any, crs: Any) -> dict:
        return {
            "side": side,
            "source": src,
            "real": src == "USER_UPLOADED_REAL",
            "dataset_name": filename,
            "crs": crs,
            "provider": "user upload" if src == "USER_UPLOADED_REAL" else "bundled synthetic sample",
            "license": None,  # unknown for uploads; never invented
            "retrieval_time": None,  # not tracked at ingest in Phase 1; absent ≠ fabricated
        }

    return {
        "status": "ok",
        "classification": classification,
        "reconciliation_mode": reconciliation_mode,
        "demo_fixture_mode": info.get("demo_fixture_mode"),
        "reconciled_parcel_count": info.get("reconciled_parcel_count"),
        "unmatched_municipal_count": info.get("unmatched_municipal_count", 0),
        "match_status_counts": info.get("match_status_counts", {}),
        "normalization_audit": info.get("normalization", {}),
        "datasets": [
            _dataset("cadastral", cad_src, info.get("cadastral_filename"), info.get("cadastral_crs")),
            _dataset("municipal", mun_src, info.get("municipal_filename"), info.get("municipal_crs")),
        ],
    }


@router.get("/api/reconciliation/{parcel_id}")
def parcel_reconciliation(parcel_id: str) -> dict:
    """Full structured evidence bundle for a single parcel (spec §18)."""
    from services.landsync_service import get_parcel_by_id

    if not is_loaded():
        raise HTTPException(
            status_code=503,
            detail="REAL_DATA_NOT_AVAILABLE: no dataset loaded. Upload and process real data first.",
        )
    try:
        parcel = get_parcel_by_id(parcel_id)
    except ParcelNotFoundError:
        raise HTTPException(status_code=404, detail=f"Parcel not found: {parcel_id!r}")
    except DataNotReadyError:  # pragma: no cover
        raise HTTPException(status_code=503, detail="REAL_DATA_NOT_AVAILABLE")

    return {
        "status": "ok",
        "parcel_id": parcel.get("parcel_id"),
        "match_status": parcel.get("match_status"),
        "reconciliation_score": parcel.get("reconciliation_score"),
        "evidence_quality": parcel.get("evidence_quality"),
        "review_required": parcel.get("review_required"),
        "review_reasons": parcel.get("review_reasons", []),
        "spatial_metrics": parcel.get("spatial_metrics", {}),
        "attribute_metrics": parcel.get("attribute_metrics", {}),
        "imagery": parcel.get("imagery", {"available": False}),
        "ml": parcel.get("ml", {"model_status": "MODEL_UNAVAILABLE"}),
        "boundaries": parcel.get("boundaries", {}),
        "recommendation": parcel.get("recommendation"),
    }
