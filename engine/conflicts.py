"""
engine/conflicts.py
===================
Conflict evaluation for a single matched parcel row.

Output schema (mandated by .agentrules):
    {
        'parcel_id':         str,
        'confidence':        int,        # 0–100
        'priority':          str,        # 'HIGH' | 'MEDIUM' | 'LOW'
        'area_difference':   float,      # signed, in m²  (area_a − area_b)
        'geometry_conflict': bool,
        'attribute_conflict': bool,
        'recommendation':    str,
    }

Confidence scoring (explainable, weights sum to 100):
    IoU similarity   → up to 60 pts   (threshold: IoU ≥ 0.95 = perfect)
    Area agreement   → up to 30 pts   (threshold: |Δarea%| ≤ 1% = perfect)
    Attribute match  → up to 10 pts   (no mismatches = perfect)

Priority thresholds:
    confidence ≥ 80  →  LOW
    confidence 50–79 →  MEDIUM
    confidence  < 50 →  HIGH
"""

from __future__ import annotations

from typing import Any

from shapely.geometry import Polygon
from shapely.geometry.base import BaseGeometry

# --------------------------------------------------------------------------- #
# Tunable thresholds (easy to unit-test and adjust)                           #
# --------------------------------------------------------------------------- #

IOU_CONFLICT_THRESHOLD: float = 0.95   # IoU below this → geometry_conflict = True
AREA_PCT_PERFECT: float = 0.01         # ≤ 1% area diff → full area score
AREA_PCT_CONFLICT: float = 0.05        # > 5% area diff → zero area score

# Confidence → priority bands
PRIORITY_HIGH_BELOW: int = 50
PRIORITY_MEDIUM_BELOW: int = 80

# Scoring weights (must sum to 100)
WEIGHT_IOU: int = 60
WEIGHT_AREA: int = 30
WEIGHT_ATTR: int = 10

# Fields that are NOT considered "attributes" for conflict detection.
# Matched against the *unsuffixed* field name (``source``, not ``source_a``).
# "source" is dataset provenance ("Cadastral_Revenue_Dept" vs
# "Municipal_Drone_Survey") — it differs *by design* between the two input
# files, so comparing it would flag attribute_conflict on every parcel.
_NON_ATTRIBUTE_FIELDS: frozenset[str] = frozenset(
    {
        "parcel_id",
        "geometry",
        "area_m2",          # source-reported area (not authoritative)
        "source",           # dataset provenance, not a parcel attribute
        "index_right",
        "index_left",
    }
)


def evaluate_conflicts(matched_row: Any) -> dict:
    """Evaluate conflicts for a single matched parcel row.

    Parameters
    ----------
    matched_row : pandas.Series or dict-like
        A single row from the GeoDataFrame produced by ``match_parcels()``.
        Must contain at minimum:
          - ``parcel_id``
          - ``geometry_a``  (Shapely geometry, EPSG:3857)
          - ``geometry_b``  (Shapely geometry, EPSG:3857)

    Returns
    -------
    dict
        Exactly the 7-key schema mandated by ``.agentrules``.

    Raises
    ------
    KeyError
        If ``parcel_id``, ``geometry_a``, or ``geometry_b`` are absent.
    ValueError
        If either geometry is null/empty.
    """
    parcel_id = _get(matched_row, "parcel_id")
    geom_a: BaseGeometry = _get(matched_row, "geometry_a")
    geom_b: BaseGeometry = _get(matched_row, "geometry_b")

    _validate_geometry(geom_a, "geometry_a", parcel_id)
    _validate_geometry(geom_b, "geometry_b", parcel_id)

    # ------------------------------------------------------------------ #
    # 1. Area difference (signed, m²)                                     #
    # ------------------------------------------------------------------ #
    area_a: float = geom_a.area
    area_b: float = geom_b.area
    area_difference: float = float(area_a - area_b)

    # ------------------------------------------------------------------ #
    # 2. Geometric IoU                                                     #
    # ------------------------------------------------------------------ #
    iou: float = _compute_iou(geom_a, geom_b)
    geometry_conflict: bool = iou < IOU_CONFLICT_THRESHOLD

    # ------------------------------------------------------------------ #
    # 3. Attribute conflict detection                                      #
    # ------------------------------------------------------------------ #
    attribute_conflict: bool = _detect_attribute_conflict(matched_row)

    # ------------------------------------------------------------------ #
    # 4. Explainable confidence score (0–100)                             #
    # ------------------------------------------------------------------ #
    confidence: int = _score_confidence(
        iou=iou,
        area_a=area_a,
        area_difference=area_difference,
        attribute_conflict=attribute_conflict,
    )

    # ------------------------------------------------------------------ #
    # 5. Priority                                                         #
    # ------------------------------------------------------------------ #
    priority: str = _assign_priority(confidence)

    # ------------------------------------------------------------------ #
    # 6. Human-readable recommendation                                    #
    # ------------------------------------------------------------------ #
    recommendation: str = _build_recommendation(
        geometry_conflict=geometry_conflict,
        attribute_conflict=attribute_conflict,
        area_difference=area_difference,
        area_a=area_a,
        iou=iou,
        confidence=confidence,
    )

    # ------------------------------------------------------------------ #
    # 7. Assemble output — exact schema from .agentrules                  #
    # ------------------------------------------------------------------ #
    result = {
        "parcel_id": str(parcel_id),
        "confidence": int(confidence),
        "priority": priority,
        "area_difference": float(area_difference),
        "geometry_conflict": bool(geometry_conflict),
        "attribute_conflict": bool(attribute_conflict),
        "recommendation": str(recommendation),
    }

    _validate_output_schema(result)
    return result


# --------------------------------------------------------------------------- #
# Scoring sub-functions                                                        #
# --------------------------------------------------------------------------- #

def _compute_iou(geom_a: BaseGeometry, geom_b: BaseGeometry) -> float:
    """Compute Intersection over Union between two Shapely geometries.

    Returns
    -------
    float
        IoU in [0.0, 1.0]. Returns 0.0 if the union area is zero.
    """
    try:
        intersection_area: float = geom_a.intersection(geom_b).area
        union_area: float = geom_a.union(geom_b).area
    except Exception:
        return 0.0

    if union_area == 0.0:
        return 0.0
    return float(intersection_area / union_area)


def _detect_attribute_conflict(matched_row: Any) -> bool:
    """Return True if any non-geometry attribute differs between _a / _b columns.

    Looks for paired columns named ``<field>_a`` / ``<field>_b`` and
    compares their values, skipping columns in ``_NON_ATTRIBUTE_COLS``.
    """
    try:
        keys = list(matched_row.keys())
    except AttributeError:
        return False

    _a_cols = {k[:-2] for k in keys if k.endswith("_a")}
    _b_cols = {k[:-2] for k in keys if k.endswith("_b")}
    shared_fields = _a_cols & _b_cols

    for field in shared_fields:
        col_a = f"{field}_a"
        col_b = f"{field}_b"
        # Compare the unsuffixed field name against the exclusion list —
        # suffixed names (``source_a``) would never match otherwise.
        if field in _NON_ATTRIBUTE_FIELDS:
            continue
        val_a = matched_row[col_a]
        val_b = matched_row[col_b]
        # Treat NaN == NaN as no conflict.
        try:
            import math
            if math.isnan(val_a) and math.isnan(val_b):  # type: ignore[arg-type]
                continue
        except (TypeError, ValueError):
            pass
        if val_a != val_b:
            return True

    return False


def _score_confidence(
    *,
    iou: float,
    area_a: float,
    area_difference: float,
    attribute_conflict: bool,
) -> int:
    """Compute explainable confidence score in [0, 100].

    Weights
    -------
    IoU similarity   : 60 pts
    Area agreement   : 30 pts
    Attribute match  : 10 pts
    """
    # --- IoU component (0–60) ---
    iou_score: float = min(iou, 1.0) * WEIGHT_IOU

    # --- Area component (0–30) ---
    if area_a > 0:
        area_pct: float = abs(area_difference) / area_a
    else:
        area_pct = 0.0 if area_difference == 0 else 1.0

    if area_pct <= AREA_PCT_PERFECT:
        area_score: float = float(WEIGHT_AREA)
    elif area_pct >= AREA_PCT_CONFLICT:
        area_score = 0.0
    else:
        # Linear interpolation between thresholds.
        span = AREA_PCT_CONFLICT - AREA_PCT_PERFECT
        area_score = WEIGHT_AREA * (1.0 - (area_pct - AREA_PCT_PERFECT) / span)

    # --- Attribute component (0–10) ---
    attr_score: float = 0.0 if attribute_conflict else float(WEIGHT_ATTR)

    raw = iou_score + area_score + attr_score
    return int(max(0, min(100, round(raw))))


def _assign_priority(confidence: int) -> str:
    """Map confidence score to priority string."""
    if confidence < PRIORITY_HIGH_BELOW:
        return "HIGH"
    if confidence < PRIORITY_MEDIUM_BELOW:
        return "MEDIUM"
    return "LOW"


def _build_recommendation(
    *,
    geometry_conflict: bool,
    attribute_conflict: bool,
    area_difference: float,
    area_a: float,
    iou: float,
    confidence: int,
) -> str:
    """Compose a human-readable recommendation string."""
    if geometry_conflict and attribute_conflict:
        return (
            "Geometry and attribute conflicts detected — "
            "manual review required before merging."
        )
    if geometry_conflict:
        pct = abs(area_difference) / area_a * 100 if area_a else 0.0
        return (
            f"Geometry conflict detected (IoU={iou:.3f}, "
            f"area delta={abs(area_difference):.1f} m² / {pct:.1f}%) — "
            "verify boundary source data."
        )
    if attribute_conflict:
        return (
            "Attribute mismatch detected with consistent geometry — "
            "reconcile metadata fields."
        )
    if confidence >= PRIORITY_MEDIUM_BELOW:
        return "Records are consistent — no action needed."
    area_pct = abs(area_difference) / area_a * 100 if area_a else 0.0
    return (
        f"Minor discrepancy (area delta={abs(area_difference):.1f} m² / "
        f"{area_pct:.1f}%) — verify source data for accuracy."
    )


# --------------------------------------------------------------------------- #
# Validation helpers                                                           #
# --------------------------------------------------------------------------- #

def _get(row: Any, key: str) -> Any:
    """Access *key* from a Series or dict, raising KeyError on miss."""
    try:
        return row[key]
    except KeyError:
        raise KeyError(
            f"matched_row is missing required field {key!r}. "
            f"Available keys: {list(row.keys()) if hasattr(row, 'keys') else '?'}"
        )


def _validate_geometry(geom: Any, name: str, parcel_id: Any) -> None:
    """Raise ValueError if *geom* is None or empty."""
    if geom is None or (hasattr(geom, "is_empty") and geom.is_empty):
        raise ValueError(
            f"Parcel {parcel_id!r}: {name} is null or empty. "
            "Cannot evaluate conflicts on missing geometry."
        )


_REQUIRED_KEYS: tuple[str, ...] = (
    "parcel_id",
    "confidence",
    "priority",
    "area_difference",
    "geometry_conflict",
    "attribute_conflict",
    "recommendation",
)
_VALID_PRIORITIES: frozenset[str] = frozenset({"HIGH", "MEDIUM", "LOW"})


def _validate_output_schema(result: dict) -> None:
    """Assert that *result* matches the exact schema from .agentrules.

    Raises
    ------
    RuntimeError
        If the output is missing a key, has a wrong type, or has an
        invalid priority value.
    """
    for key in _REQUIRED_KEYS:
        if key not in result:
            raise RuntimeError(f"Output missing required key: {key!r}")

    type_map = {
        "parcel_id": str,
        "confidence": int,
        "priority": str,
        "area_difference": float,
        "geometry_conflict": bool,
        "attribute_conflict": bool,
        "recommendation": str,
    }
    for key, expected_type in type_map.items():
        if not isinstance(result[key], expected_type):
            raise RuntimeError(
                f"Output[{key!r}] expected {expected_type.__name__}, "
                f"got {type(result[key]).__name__}."
            )

    if result["priority"] not in _VALID_PRIORITIES:
        raise RuntimeError(
            f"Output['priority'] must be one of {sorted(_VALID_PRIORITIES)}, "
            f"got {result['priority']!r}."
        )
