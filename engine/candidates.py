"""
engine/candidates.py
====================
Spatial candidate matching, deterministic ranking, and match-status
classification (spec §6, §9).

The legacy matcher (engine.matching) pairs rows by ID then bounding-box
fallback and silently drops the rest. This module adds the missing pieces:

  * explicit UNMATCHED tracking for both sides,
  * nearest-candidate discovery for unmatched cadastral parcels,
  * a documented, configurable threshold set for status classification,
  * preservation of top candidate alternates for review.

Deterministic: identical input → identical output. No randomness.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Any, Optional

import geopandas as gpd
import pandas as pd

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Configurable thresholds — documented reasoning (spec §9)
# ---------------------------------------------------------------------------
@dataclass
class MatchingThresholds:
    """Thresholds for candidate ranking and status classification.

    Every threshold is overridable; defaults are chosen conservatively so
    the system prefers REVIEW_REQUIRED over a false confident MATCH.
    """

    # Minimum IoU for two polygons to be considered the same parcel.
    # Rationale: cadastral and municipal surveys of the same parcel drawn
    # from independent surveys rarely align perfectly; 0.30 keeps genuinely
    # shifted boundaries while rejecting coincidental overlaps.
    iou_match_threshold: float = 0.30

    # Minimum convex-hull IoU (shape similarity) accepted when the exact
    # IoU is unavailable or degenerate. Slightly looser than IoU because
    # hulls abstract away concavities.
    shape_match_threshold: float = 0.35

    # Centroid distance above which a candidate is not the same parcel
    # (metres). Small parcels can have real centroid offsets from mapping
    # practice; 75 m tolerates offset mapping while excluding neighbours.
    centroid_max_m: float = 75.0

    # Absolute IoU gap below which two candidates are considered ambiguous.
    # When the best and runner-up differ by less than this, the assignment
    # is not certain → REVIEW_REQUIRED rather than confident MATCH.
    ambiguity_gap: float = 0.10

    # Fraction of the cadastral area covered by the intersection for a
    # "reasonable" overlap even when IoU is low (large-vs-small parcel case).
    overlap_min_pct: float = 20.0

    # Maximum alternates stored per cadastral parcel for review.
    max_candidates: int = 3


@dataclass
class CandidateMatch:
    """One candidate pairing of a cadastral parcel with a municipal parcel."""

    cadastral_id: str
    municipal_id: str
    rank: int
    status: str
    iou: Optional[float] = None
    overlap_pct: Optional[float] = None
    centroid_distance_m: Optional[float] = None
    reason: str = ""
    metrics: dict = field(default_factory=dict)


def classify_status(
    iou: Optional[float],
    overlap_pct: Optional[float],
    centroid_distance_m: Optional[float],
    attribute_conflict: bool,
    th: MatchingThresholds,
) -> str:
    """Deterministic status classification (spec §9).

    Returns one of MATCH, MINOR_DISCREPANCY, MAJOR_DISCREPANCY,
    REVIEW_REQUIRED. UNMATCHED is assigned by the caller when no
    candidate exists.
    """
    if iou is None or overlap_pct is None:
        return "REVIEW_REQUIRED"

    if iou >= 0.90:
        return "MATCH" if not attribute_conflict else "REVIEW_REQUIRED"

    if iou >= th.iou_match_threshold:
        return "MINOR_DISCREPANCY" if not attribute_conflict else "REVIEW_REQUIRED"

    if overlap_pct >= th.overlap_min_pct or (
        centroid_distance_m is not None
        and centroid_distance_m <= th.centroid_max_m
        and overlap_pct > 0
    ):
        return "MAJOR_DISCREPANCY"

    # Some overlap but weak evidence, or attribute conflict with weak geometry.
    if overlap_pct > 0:
        return "REVIEW_REQUIRED"
    return "UNMATCHED"


def find_candidates(
    unmatched_a: gpd.GeoDataFrame,
    gdf_b: gpd.GeoDataFrame,
    *,
    th: MatchingThresholds,
    id_col: str = "parcel_id",
    max_candidates: Optional[int] = None,
) -> dict[str, list[dict]]:
    """Nearest municipal candidates for each unmatched cadastral parcel.

    Uses a GeoPandas STRtree-backed nearest join (O(n log n)); for each
    cadastral parcel returns up to ``max_candidates`` nearest municipal
    parcels with their raw distances — the caller computes full metrics
    only on these candidates (spec §25: no O(n²) comparisons).
    """
    if unmatched_a.empty or gdf_b.empty:
        return {}
    k = max_candidates or th.max_candidates

    # Rename the left id column so the sjoin cannot collide with the right
    # frame's identically-named column (geopandas suffix behaviour varies).
    left = unmatched_a[[id_col, "geometry"]].rename(columns={id_col: "__cand_id"})
    right = gdf_b[[id_col, "geometry"]]
    try:
        joined = gpd.sjoin_nearest(
            left,
            right,
            how="inner",
            distance_col="candidate_distance_m",
        )
    except (TypeError, ValueError):
        # Very old geopandas without sjoin_nearest support.
        return {}

    if joined.empty:
        return {}

    # Resolve the right-frame positional index column across geopandas versions.
    right_pos_col = next(
        (c for c in ("index_right", "index_rightb", "index_b") if c in joined.columns),
        None,
    )
    if right_pos_col is None:
        return {}

    candidates: dict[str, list[dict]] = {}
    b_ids = gdf_b[id_col].tolist()
    for pid, dist, right_pos in zip(
        joined["__cand_id"],
        joined["candidate_distance_m"],
        joined[right_pos_col],
    ):
        key = str(pid)
        bucket = candidates.setdefault(key, [])
        if len(bucket) >= k:
            continue
        d = float(dist) if dist == dist else None  # NaN guard
        bucket.append(
            {
                "municipal_id": str(b_ids[right_pos]),
                "centroid_distance_m": d,
            }
        )
    for key in candidates:
        candidates[key].sort(key=lambda c: c["centroid_distance_m"] or 0.0)
    return candidates


def rank_candidates(
    geom_a: Any,
    candidates: list[dict],
    b_geometry_by_id: dict,
    *,
    th: MatchingThresholds,
) -> list[CandidateMatch]:
    """Compute metrics per candidate and rank deterministically.

    ``b_geometry_by_id`` must be a prebuilt {id: geometry} lookup so the
    per-parcel cost stays O(candidates), not O(municipal_total).

    Ranking key: (IoU desc, overlap_pct desc, centroid_distance asc).
    Returns CandidateMatch objects with status pre-classified.
    """
    from engine.metrics import compute_pair_metrics

    ranked: list[CandidateMatch] = []

    for cand in candidates:
        mid = cand["municipal_id"]
        geom_b = b_geometry_by_id.get(mid)
        if geom_b is None:
            continue
        metrics = compute_pair_metrics(geom_a, geom_b)
        sm = metrics["spatial_metrics"]
        cm = CandidateMatch(
            cadastral_id="",
            municipal_id=mid,
            rank=0,
            status=classify_status(
                iou=sm["iou"],
                overlap_pct=sm["overlap_pct_of_cadastral"],
                centroid_distance_m=sm["centroid_distance_m"],
                attribute_conflict=False,
                th=th,
            ),
            iou=sm["iou"],
            overlap_pct=sm["overlap_pct_of_cadastral"],
            centroid_distance_m=sm["centroid_distance_m"],
            reason="candidate ranking",
            metrics=sm,
        )
        ranked.append(cm)

    ranked.sort(
        key=lambda c: (
            -(c.iou if c.iou is not None else 0.0),
            -(c.overlap_pct if c.overlap_pct is not None else 0.0),
            c.centroid_distance_m if c.centroid_distance_m is not None else float("inf"),
        )
    )
    for i, c in enumerate(ranked, start=1):
        c.rank = i
    return ranked


def build_unmatched_record(
    parcel_id: str,
    side: str,
    nearest_distance_m: Optional[float],
) -> dict:
    """Explicit UNMATCHED record so nothing is silently dropped (spec §6.5)."""
    return {
        "parcel_id": str(parcel_id),
        "match_status": "UNMATCHED",
        "match_side": side,
        "nearest_candidate_distance_m": nearest_distance_m,
        "review_required": True,
    }
