"""
engine/metrics.py
=================
Deterministic GIS evidence metrics for a matched parcel pair.

Every function here is pure: same inputs → bit-identical outputs.
No rounding happens in this module — raw float values are returned and
rounding is deferred to presentation layers only (spec §8).

All geometries MUST be in a projected metric CRS (EPSG:3857) before
being passed here; callers are responsible for normalisation
(engine.crs.CRSManager).
"""

from __future__ import annotations

import math
from typing import Any, Optional

from shapely.geometry.base import BaseGeometry

# Number of boundary vertices of geom_a sampled for boundary displacement.
# Deterministic sampling: evenly spaced indices, always includes vertex 0.
_BOUNDARY_SAMPLE_COUNT = 64


def _safe(value: float) -> Optional[float]:
    """Return None for NaN/inf, else the float — JSON cannot carry NaN."""
    if value is None:
        return None
    try:
        f = float(value)
    except (TypeError, ValueError):
        return None
    if math.isnan(f) or math.isinf(f):
        return None
    return f


def _compactness(geom: BaseGeometry) -> Optional[float]:
    """Polsby–Popper compactness: 4π·area / perimeter².

    1.0 for a perfect circle; dimensionless and CRS-metric dependent
    (valid for projected metric CRS only).
    """
    try:
        perimeter = geom.length
        if perimeter <= 0:
            return None
        return float(4.0 * math.pi * geom.area / (perimeter * perimeter))
    except Exception:
        return None


def _boundary_displacement(geom_a: BaseGeometry, geom_b: BaseGeometry) -> Optional[float]:
    """Mean distance from geom_a's boundary vertices to geom_b's boundary.

    Deterministic: samples geom_a's exterior ring at evenly spaced indices
    (no randomness). Metres in a projected metric CRS.
    """
    try:
        from shapely.geometry import Point

        ring = geom_a.exterior
        coords = list(ring.coords)
        n = len(coords)
        if n == 0:
            return None
        count = min(_BOUNDARY_SAMPLE_COUNT, n)
        step = max(1, n // count)
        dists = []
        for i in range(0, n, step):
            dists.append(Point(coords[i]).distance(geom_b.exterior))
        if not dists:
            return None
        return float(sum(dists) / len(dists))
    except Exception:
        return None


def compute_pair_metrics(
    geom_a: BaseGeometry,
    geom_b: BaseGeometry,
    attrs_a: Optional[dict] = None,
    attrs_b: Optional[dict] = None,
    imagery_evidence: Optional[dict] = None,
) -> dict:
    """Compute the full deterministic evidence bundle for one pair.

    Parameters
    ----------
    geom_a, geom_b : shapely geometry
        Parcel boundaries in a projected metric CRS (EPSG:3857).
    attrs_a, attrs_b : dict, optional
        Non-geometry attributes of each source, used for attribute
        agreement metrics. Missing fields yield None (never a guess).
    imagery_evidence : dict, optional
        Real imagery provenance/observation facts if available.
        Absent imagery yields ``available: False`` — never fabricated.

    Returns
    -------
    dict
        ``spatial_metrics`` (raw floats), ``attribute_metrics``,
        ``imagery`` — see spec §7/§18. All values reproducible.
    """
    attrs_a = attrs_a or {}
    attrs_b = attrs_b or {}
    imagery_evidence = imagery_evidence or {}

    area_a = _safe(geom_a.area)
    area_b = _safe(geom_b.area)
    perimeter_a = _safe(geom_a.length)
    perimeter_b = _safe(geom_b.length)

    centroid_a = geom_a.centroid
    centroid_b = geom_b.centroid
    centroid_distance = _safe(centroid_a.distance(centroid_b))

    try:
        intersection = geom_a.intersection(geom_b)
        union = geom_a.union(geom_b)
        intersection_area = _safe(intersection.area)
        union_area = _safe(union.area)
    except Exception:
        intersection_area = None
        union_area = None

    iou: Optional[float] = None
    if intersection_area is not None and union_area:
        iou = _safe(intersection_area / union_area)

    area_difference = (
        _safe(abs(area_a - area_b))
        if area_a is not None and area_b is not None
        else None
    )
    area_ratio = (
        _safe(min(area_a, area_b) / max(area_a, area_b))
        if area_a and area_b
        else None
    )

    perimeter_difference = (
        _safe(abs(perimeter_a - perimeter_b))
        if perimeter_a is not None and perimeter_b is not None
        else None
    )

    try:
        hausdorff = _safe(geom_a.hausdorff_distance(geom_b))
    except Exception:
        hausdorff = None

    boundary_difference = _boundary_displacement(geom_a, geom_b)

    overlap_pct_a = (
        _safe(intersection_area / area_a * 100.0)
        if intersection_area is not None and area_a
        else None
    )
    overlap_pct_b = (
        _safe(intersection_area / area_b * 100.0)
        if intersection_area is not None and area_b
        else None
    )

    compactness_a = _compactness(geom_a)
    compactness_b = _compactness(geom_b)
    compactness_difference = (
        _safe(abs(compactness_a - compactness_b))
        if compactness_a is not None and compactness_b is not None
        else None
    )

    # Shape similarity: IoU of the two convex hulls — captures how alike the
    # overall shapes are irrespective of interior concavities. Deterministic.
    shape_similarity = None
    try:
        hull_union = geom_a.convex_hull.union(geom_b.convex_hull).area
        if hull_union:
            hull_intersection = geom_a.convex_hull.intersection(
                geom_b.convex_hull
            ).area
            shape_similarity = _safe(hull_intersection / hull_union)
    except Exception:
        shape_similarity = None

    spatial_metrics = {
        "cadastral_area_m2": area_a,
        "municipal_area_m2": area_b,
        "area_difference_m2": area_difference,
        "area_ratio": area_ratio,
        "perimeter_difference_m": perimeter_difference,
        "centroid_distance_m": centroid_distance,
        "intersection_area_m2": intersection_area,
        "union_area_m2": union_area,
        "iou": iou,
        "overlap_pct_of_cadastral": overlap_pct_a,
        "overlap_pct_of_municipal": overlap_pct_b,
        "hausdorff_distance_m": hausdorff,
        "boundary_displacement_m": boundary_difference,
        "compactness_cadastral": compactness_a,
        "compactness_municipal": compactness_b,
        "compactness_difference": compactness_difference,
        "shape_similarity": shape_similarity,
        "vertex_count_cadastral": _vertex_count(geom_a),
        "vertex_count_municipal": _vertex_count(geom_b),
    }

    attribute_metrics = _attribute_agreement(attrs_a, attrs_b)
    imagery_block = _imagery_block(imagery_evidence)

    return {
        "spatial_metrics": spatial_metrics,
        "attribute_metrics": attribute_metrics,
        "imagery": imagery_block,
    }


def _vertex_count(geom: BaseGeometry) -> Optional[int]:
    try:
        if geom.geom_type == "Polygon":
            return len(geom.exterior.coords)
        if geom.geom_type == "MultiPolygon":
            return sum(len(p.exterior.coords) for p in geom.geoms)
        return len(geom.coords) if hasattr(geom, "coords") else None
    except Exception:
        return None


def _attribute_agreement(attrs_a: dict, attrs_b: dict) -> dict:
    """Compare the documented reconcilable attributes honestly.

    Only fields present in BOTH sources produce a boolean; missing fields
    yield None (unknown) — never a fabricated match/mismatch.
    """
    comparable = ("survey_number", "land_use", "classification", "owner")
    out: dict[str, Optional[bool]] = {}
    for field in comparable:
        va = attrs_a.get(field)
        vb = attrs_b.get(field)
        if va is None or vb is None:
            out[f"{field}_match"] = None
        else:
            out[f"{field}_match"] = _norm(va) == _norm(vb)
    return out


def _norm(v: Any) -> str:
    return str(v).strip().lower()


def _imagery_block(imagery_evidence: dict) -> dict:
    """Normalise imagery evidence — explicit 'unavailable' when absent."""
    if not imagery_evidence:
        return {
            "available": False,
            "acquisition_date": None,
            "resolution_m_per_px": None,
            "observed_change": None,
            "note": "No configured imagery evidence for this parcel.",
        }
    return {
        "available": bool(imagery_evidence.get("available", True)),
        "acquisition_date": imagery_evidence.get("acquired"),
        "resolution_m_per_px": imagery_evidence.get("resolution_m_per_px"),
        "observed_change": imagery_evidence.get("observed_change"),
        "provider": imagery_evidence.get("provider"),
        "sensor": imagery_evidence.get("sensor"),
    }
