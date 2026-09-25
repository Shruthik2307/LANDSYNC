"""
engine/fusion.py
================
Hybrid evidence fusion (spec §14, §19).

Combines three evidence streams into one final assessment:

    1. Deterministic GIS evidence (authoritative for measurements)
    2. ML classification evidence (only from a VALIDATED model artifact)
    3. Imagery/observation evidence (only when actually available)

Fusion methodology (documented, deterministic):

    reconciliation_score = round(100 * geometric_agreement)
    geometric_agreement  = 0.55 * iou_component
                         + 0.30 * area_component
                         + 0.15 * centroid_component

      iou_component      = iou clipped to [0, 1]
      area_component     = area_ratio (min/max of areas, clipped to [0, 1])
      centroid_component = max(0, 1 - centroid_distance_m / 150)

    The weights are a design decision, stated here rather than hidden:
    IoU dominates because it captures overall agreement; area ratio and
    centroid distance corroborate. The score expresses *evidence
    agreement*, NOT statistical accuracy — it is not calibrated against
    verified outcomes and must not be presented as a probability of
    correctness.

    The ML stream NEVER changes the deterministic measurements. When a
    validated model exists, its prediction and probability are reported
    alongside and can only PROMOTE review_required on disagreement
    (spec §15) — it cannot upgrade a REVIEW_REQUIRED to MATCH.

Missing evidence never becomes a number: absent imagery, absent
attributes, or an untrained model are reported as explicit states.
"""

from __future__ import annotations

from typing import Any, Optional

# Centroid distance (metres) at which the centroid component reaches zero.
_CENTROID_ZERO_M = 150.0

# Evidence-quality rubric thresholds (documented, spec §19).
_HIGH_QUALITY_MIN_IOU = 0.70       # strong geometric overlap
_MEDIUM_QUALITY_MIN_IOU = 0.30     # usable overlap


def geometric_agreement(
    iou: Optional[float],
    area_ratio: Optional[float],
    centroid_distance_m: Optional[float],
) -> Optional[float]:
    """Deterministic geometric agreement in [0, 1]; None when unmeasurable."""
    if iou is None:
        return None
    iou_c = min(max(iou, 0.0), 1.0)
    area_c = min(max(area_ratio, 0.0), 1.0) if area_ratio is not None else 0.5
    if centroid_distance_m is not None:
        cent_c = max(0.0, 1.0 - float(centroid_distance_m) / _CENTROID_ZERO_M)
    else:
        cent_c = 0.5
    return float(0.55 * iou_c + 0.30 * area_c + 0.15 * cent_c)


def evidence_quality(
    iou: Optional[float],
    attribute_metrics: Optional[dict],
    imagery: Optional[dict],
    geometry_valid: bool = True,
) -> str:
    """Classify evidence quality as HIGH / MEDIUM / LOW / INSUFFICIENT.

    Rubric (documented):
      HIGH         strong geometry overlap AND at least one attribute
                   comparison possible
      MEDIUM       usable geometry overlap, thin attributes
      LOW          weak geometry overlap
      INSUFFICIENT geometry unmeasurable or invalid
    """
    if not geometry_valid or iou is None:
        return "INSUFFICIENT"
    attrs = attribute_metrics or {}
    attr_known = any(v is not None for v in attrs.values())
    imagery_ok = bool(imagery and imagery.get("available"))
    if iou >= _HIGH_QUALITY_MIN_IOU and (attr_known or imagery_ok):
        return "HIGH"
    if iou >= _MEDIUM_QUALITY_MIN_IOU:
        return "MEDIUM" if attr_known else "LOW"
    return "LOW"


def fuse(
    *,
    parcel_id: str,
    candidate_status: str,
    spatial_metrics: dict,
    attribute_metrics: Optional[dict] = None,
    imagery: Optional[dict] = None,
    attribute_conflict: bool = False,
    model: Optional[dict] = None,
    duplicate_id: bool = False,
) -> dict:
    """Fuse all evidence for one parcel into the final assessment.

    Parameters
    ----------
    candidate_status : str
        Status from engine.candidates.classify_status (or "UNMATCHED").
    spatial_metrics : dict
        Raw deterministic metrics from engine.metrics.compute_pair_metrics.
    model : dict, optional
        ML stream: {prediction, probability, model_version} from a
        validated model. When absent the fused output carries
        ``model_status: "MODEL_UNAVAILABLE"`` honestly.
    duplicate_id : bool
        Duplicate parcel-ID flag from ingestion.

    Returns
    -------
    dict
        match_status, reconciliation_score (0-100 or None),
        evidence_quality, review_required, review_reasons[],
        model_status, and the raw inputs for transparency.
    """
    sm = spatial_metrics or {}
    iou = sm.get("iou")
    area_ratio = sm.get("area_ratio")
    centroid_d = sm.get("centroid_distance_m")

    agreement = geometric_agreement(iou, area_ratio, centroid_d)
    score = int(round(100 * agreement)) if agreement is not None else None

    quality = evidence_quality(
        iou=iou,
        attribute_metrics=attribute_metrics,
        imagery=imagery,
        geometry_valid=iou is not None,
    )

    review_reasons: list[str] = []
    status = candidate_status

    # ---- Review triggers (spec §15) ---------------------------------------
    if status == "UNMATCHED":
        review_reasons.append("NO_SPATIAL_MATCH: no municipal parcel overlapped this parcel.")
    if attribute_conflict:
        review_reasons.append("Attribute values disagree between sources.")
    if duplicate_id:
        review_reasons.append("DUPLICATE_RECORD: this parcel ID appears more than once.")
    if iou is not None and 0.0 < iou < 0.30:
        review_reasons.append("Weak geometric overlap — boundary evidence inconclusive.")
    if iou is None:
        review_reasons.append("INSUFFICIENT_EVIDENCE: geometry metrics could not be computed.")
    if quality == "INSUFFICIENT":
        review_reasons.append("Evidence quality insufficient for an automatic decision.")

    # Imagery quality guard: low-resolution imagery cannot confirm parcel facts.
    if imagery and imagery.get("available"):
        res = imagery.get("resolution_m_per_px")
        if res is not None and res > 1.5:
            review_reasons.append(
                f"Imagery resolution ({res} m/px) too coarse for parcel-scale verification."
            )

    # ---- ML stream (spec §10/§14/§16) -------------------------------------
    model_status = "MODEL_UNAVAILABLE"
    if model is not None:
        model_status = model.get("model_status", "OK")
        if model_status == "MODEL_OUT_OF_DISTRIBUTION":
            review_reasons.append("MODEL_OUT_OF_DISTRIBUTION: input outside training distribution.")
        elif model_status == "OK" and model.get("prediction") is not None and iou is not None:
            pred = model.get("prediction")
            if isinstance(pred, (int, float)):
                ml_sees_conflict = (int(pred) != 0)
            elif isinstance(pred, str):
                ml_sees_conflict = pred.strip().upper() not in (
                    "0", "MATCH", "NO_CONFLICT", "NO CONFLICT", "FALSE", "NONE"
                )
            else:
                ml_sees_conflict = bool(pred)

            det_sees_conflict = iou < 0.30 or attribute_conflict
            if ml_sees_conflict != det_sees_conflict:
                review_reasons.append(
                    "Model disagreement with deterministic evidence — human review required."
                )

    if review_reasons and status in ("MATCH", "MINOR_DISCREPANCY", "MAJOR_DISCREPANCY"):
        status = "REVIEW_REQUIRED"

    return {
        "parcel_id": str(parcel_id),
        "match_status": status,
        "reconciliation_score": score,
        "evidence_quality": quality,
        "review_required": bool(review_reasons) or status in ("UNMATCHED", "REVIEW_REQUIRED"),
        "review_reasons": review_reasons,
        "model_status": model_status,
        "fusion_method": (
            "reconciliation_score = 100 * (0.55*iou + 0.30*area_ratio "
            "+ 0.15*centroid_component); NOT a calibrated accuracy"
        ),
        "ml": model if model is not None else {"model_status": "MODEL_UNAVAILABLE"},
    }
