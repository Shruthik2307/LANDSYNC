"""
backend/routes/labeling.py
==========================
Human-review labeling workflow (spec §4).

GET    /api/labeling/queue   — parcel comparisons awaiting review, with both
                               geometries, deterministic metrics, imagery
                               provenance, and dataset provenance. The engine's
                               own match_status is DISPLAYED as evidence but is
                               NEVER auto-converted into a label.
POST   /api/labeling/submit  — append a verified label to
                               data/verified/labels.jsonl (schema-validated,
                               duplicate-rejecting, synthetic-provenance-rejecting).
GET    /api/labeling/report  — dataset quality report (spec §8).

The store lives in backend/services/label_store.py so the CLI tools share the exact
same validation rules as the API.
"""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from fastapi import APIRouter, HTTPException
from fastapi.responses import FileResponse
from pydantic import BaseModel, Field

from services.label_store import (
    SCHEMA_VERSION,
    LabelStoreError,
    append_label,
    load_labels,
)

router = APIRouter(tags=["labeling"])

_QUEUE_LIMIT = 200  # bounded response (spec §25)

_REVIEWER_PAGE = Path(__file__).resolve().parent.parent / "static" / "reviewer.html"


@router.get("/reviewer")
def reviewer_page() -> Any:
    """Serve the human-review UI (static, no secrets)."""
    if not _REVIEWER_PAGE.exists():
        raise HTTPException(status_code=404, detail="Reviewer page not deployed")
    return FileResponse(_REVIEWER_PAGE, media_type="text/html")


class LabelSubmission(BaseModel):
    cadastral_id: str
    municipal_id: str
    region: str
    label: str = Field(
        description="MATCH | MINOR_DISCREPANCY | MAJOR_DISCREPANCY | UNMATCHED | REVIEW"
    )
    review_status: str = "verified"
    reviewer: str = Field(min_length=1)
    evidence_source: str
    pair_metrics: dict = Field(default_factory=dict)
    notes: str = ""


def _iter_comparison_pairs() -> list[dict]:
    """Reconstruct parcel-pair comparisons from the loaded engine cache."""
    from services.landsync_service import _cache

    pairs: list[dict] = []
    for p in _cache.all_parcels():
        boundaries = p.get("boundaries", {})
        if not boundaries.get("cadastral"):
            continue
        pairs.append(
            {
                "cadastral_id": p["parcel_id"],
                "municipal_id": p.get("candidate_match_id") or p["parcel_id"],
                "engine_match_status": p.get("match_status"),
                "reconciliation_score": p.get("reconciliation_score"),
                "spatial_metrics": p.get("spatial_metrics", {}),
                "attribute_metrics": p.get("attribute_metrics", {}),
                "imagery": p.get("imagery", {"available": False}),
                "boundaries": boundaries,
                "recommendation": p.get("recommendation"),
            }
        )
    return pairs


def _dataset_provenance() -> dict:
    from services.landsync_service import get_dataset_info

    info = get_dataset_info()
    return {
        "cadastral_source": info.get("cadastral_source", "sample"),
        "cadastral_filename": info.get("cadastral_filename"),
        "municipal_source": info.get("municipal_source", "sample"),
        "municipal_filename": info.get("municipal_filename"),
        "cadastral_crs": info.get("cadastral_crs"),
        "municipal_crs": info.get("municipal_crs"),
        "normalization_audit": info.get("normalization", {}),
    }


def _region_for_dataset() -> str:
    """Region label for label records — derived from dataset provenance."""
    from services.landsync_service import get_dataset_info

    info = get_dataset_info()
    name = info.get("cadastral_filename") or "unknown"
    if info.get("cadastral_source") == "upload":
        return f"upload:{name}"
    return f"sample:{name}"


@router.get("/api/labeling/queue")
def labeling_queue() -> dict:
    """Comparisons awaiting human review, with full evidence."""
    from services.landsync_service import is_loaded

    if not is_loaded():
        return {
            "status": "REAL_DATA_NOT_AVAILABLE",
            "detail": "No dataset loaded. Upload real data first, then review.",
            "pairs": [],
        }

    pairs = _iter_comparison_pairs()
    return {
        "status": "ok",
        "count": len(pairs[:_QUEUE_LIMIT]),
        "total_pairs": len(pairs),
        "dataset_provenance": _dataset_provenance(),
        "suggested_region": _region_for_dataset(),
        # Engine status shown as evidence only — labeling is human decision.
        "label_options": [
            "MATCH",
            "MINOR_DISCREPANCY",
            "MAJOR_DISCREPANCY",
            "UNMATCHED",
            "REVIEW",
        ],
        "pairs": pairs[:_QUEUE_LIMIT],
    }


@router.post("/api/labeling/submit")
def labeling_submit(submission: LabelSubmission) -> dict:
    """Append a human-verified label (validated, dedupe, anti-synthetic)."""
    from services.landsync_service import is_loaded

    if not is_loaded():
        raise HTTPException(
            status_code=503,
            detail="REAL_DATA_NOT_AVAILABLE: load a real dataset before labeling.",
        )

    record = {
        "schema_version": SCHEMA_VERSION,
        "cadastral_id": submission.cadastral_id,
        "municipal_id": submission.municipal_id,
        "region": submission.region,
        "label": submission.label,
        "review_status": submission.review_status,
        "reviewer": submission.reviewer,
        "evidence_source": submission.evidence_source,
        "pair_metrics": submission.pair_metrics,
        "notes": submission.notes,
        "submitted_at": datetime.now(timezone.utc).isoformat(),
    }
    try:
        result = append_label(record)
    except LabelStoreError as exc:
        raise HTTPException(status_code=422, detail=str(exc))

    if not result["ok"]:
        raise HTTPException(status_code=409, detail=result["problems"][0])
    return {
        "status": "ok",
        "stored": True,
        "warnings": result["problems"],  # non-fatal validation notes
    }


@router.get("/api/labeling/report")
def labeling_report() -> dict:
    """Dataset quality report (spec §8) — honest in every state."""
    _, report = load_labels()
    from services.landsync_service import is_loaded

    report["engine_loaded"] = is_loaded()
    verified = report.get("verified_count", 0)
    report["training_ready"] = verified >= 40  # 4 classes × 10 minimum
    if verified == 0:
        report["status"] = "INSUFFICIENT_VERIFIED_DATA"
    return report
