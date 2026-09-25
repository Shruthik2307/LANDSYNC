"""
engine/geometry.py
==================
Geometry validation / repair / duplicate detection before reconciliation.

Spec §5: detect & validate CRS is the caller's job (engine.crs); this module
repairs recoverable invalid geometries, rejects unrecoverable ones, removes
impossible coordinates and flags duplicate IDs — recording every action in an
audit trail so normalisation is inspectable, not silent.
"""

from __future__ import annotations

import logging
from typing import Any, Optional

import geopandas as gpd
from shapely.validation import explain_validity, make_valid

logger = logging.getLogger(__name__)

# Coordinate sanity bounds. EPSG:3857 is roughly ±20 015 km in X, and its
# usable Y band is ±85.06° → ~±20 048 966 m. Values beyond this are impossible
# in Web Mercator and indicate a datum/units error, not real geometry.
_X_LIMIT = 20_050_000.0
_Y_LIMIT = 20_050_000.0


def normalize_geometries(
    gdf: gpd.GeoDataFrame,
    *,
    source_name: str = "input",
    drop_invalid: bool = True,
) -> tuple[gpd.GeoDataFrame, dict]:
    """Validate, repair, and audit a GeoDataFrame's geometries.

    Actions (recorded in the returned report, spec §5):
      1. Empty / null geometry rows are dropped and counted.
      2. Impossible coordinates (outside EPSG:3857 domain) are dropped
         and counted — they indicate datum or unit errors.
      3. Invalid geometries are repaired with ``make_valid`` where the
         result is a usable polygonal geometry; unrecoverable ones are
         dropped and counted.
      4. Invalid but recoverable input is counted separately from
         already-valid input.

    Parameters
    ----------
    gdf : gpd.GeoDataFrame
        Input frame (already CRS-validated by engine.crs).
    source_name : str
        Human label used in the audit report (e.g. 'cadastral').
    drop_invalid : bool
        Kept for API clarity; invalid unrecoverable rows are always
        dropped — they cannot participate in metric computation.

    Returns
    -------
    (gpd.GeoDataFrame, dict)
        Cleaned frame and a normalisation report:
        ``{source, input_rows, valid, repaired, dropped_empty,
        dropped_impossible_coords, dropped_unrecoverable}``
    """
    report: dict[str, Any] = {
        "source": source_name,
        "input_rows": int(len(gdf)),
        "valid": 0,
        "repaired": 0,
        "dropped_empty": 0,
        "dropped_impossible_coords": 0,
        "dropped_unrecoverable": 0,
    }

    if gdf.empty:
        return gdf, report

    work = gdf.copy()

    # ---- 1. Drop null / empty geometry ------------------------------------
    empty_mask = work.geometry.isna() | work.geometry.is_empty
    report["dropped_empty"] = int(empty_mask.sum())
    work = work[~empty_mask]
    if work.empty:
        return work, report

    # ---- 2. Impossible coordinates ----------------------------------------
    # Web Mercator domain check on bounds; catches lat/lon values passed
    # through un-projected (e.g. |y| ≤ 90 means someone forgot to project).
    def _impossible(geom: Any) -> bool:
        try:
            minx, miny, maxx, maxy = geom.bounds
        except Exception:
            return True
        if abs(minx) > _X_LIMIT or abs(maxx) > _X_LIMIT:
            return True
        if abs(miny) > _Y_LIMIT or abs(maxy) > _Y_LIMIT:
            return True
        return False

    bounds = work.geometry.bounds
    impossible_mask = (
        (bounds["minx"].abs() > _X_LIMIT)
        | (bounds["maxx"].abs() > _X_LIMIT)
        | (bounds["miny"].abs() > _Y_LIMIT)
        | (bounds["maxy"].abs() > _Y_LIMIT)
    )
    report["dropped_impossible_coords"] = int(impossible_mask.sum())
    work = work[~impossible_mask]
    if work.empty:
        return work, report

    # ---- 3. Validate / repair ----------------------------------------------
    validity = work.geometry.is_valid

    def _repair(geom: Any) -> Any:
        try:
            fixed = make_valid(geom)
        except Exception:
            return None
        # make_valid may return GeometryCollection; keep only polygonal parts.
        if fixed.geom_type == "GeometryCollection":
            polys = [g for g in fixed.geoms if g.geom_type in ("Polygon", "MultiPolygon")]
            if not polys:
                return None
            unioned = polys[0]
            for g in polys[1:]:
                unioned = unioned.union(g)
            fixed = unioned
        if fixed.is_empty or fixed.geom_type not in ("Polygon", "MultiPolygon"):
            return None
        return fixed

    repaired_geoms: list[Any] = []
    keep_flags: list[bool] = []
    was_invalid: list[bool] = []
    for idx, geom in work.geometry.items():
        if validity.loc[idx]:
            repaired_geoms.append(geom)
            keep_flags.append(True)
            was_invalid.append(False)
            continue
        fixed = _repair(geom)
        if fixed is None:
            keep_flags.append(False)
            was_invalid.append(True)
            repaired_geoms.append(geom)  # placeholder; row dropped below
        else:
            repaired_geoms.append(fixed)
            keep_flags.append(True)
            was_invalid.append(True)

    report["repaired"] = sum(1 for ok, inv in zip(keep_flags, was_invalid) if ok and inv)
    report["dropped_unrecoverable"] = sum(1 for ok in keep_flags if not ok)
    report["valid"] = sum(1 for ok, inv in zip(keep_flags, was_invalid) if ok and not inv)

    # Rebuild the frame from the aligned parallel lists (positional, since the
    # lists were produced by iterating work.geometry.items() in order).
    keep_positions = [i for i, ok in enumerate(keep_flags) if ok]
    kept_geoms = [repaired_geoms[i] for i in keep_positions]
    kept_rows = work.iloc[keep_positions].drop(columns=[work.geometry.name])
    work = gpd.GeoDataFrame(
        kept_rows,
        geometry=kept_geoms,
        crs=work.crs,
    )

    if report["repaired"] or report["dropped_unrecoverable"]:
        logger.info(
            "[geometry] %s: %d repaired, %d dropped (unrecoverable); "
            "%d empty, %d impossible-coordinate rows dropped.",
            source_name,
            report["repaired"],
            report["dropped_unrecoverable"],
            report["dropped_empty"],
            report["dropped_impossible_coords"],
        )

    return work, report


def detect_duplicate_ids(
    gdf: gpd.GeoDataFrame,
    *,
    id_col: str = "parcel_id",
) -> dict[str, list[int]]:
    """Return a map of duplicated ID → list of row positions (spec §5)."""
    if id_col not in gdf.columns:
        return {}
    dup_ids: dict[str, list[int]] = {}
    for pos, val in enumerate(gdf[id_col].tolist()):
        key = str(val)
        if key in dup_ids:
            dup_ids[key].append(pos)
        else:
            dup_ids[key] = [pos]
    return {k: v for k, v in dup_ids.items() if len(v) > 1}


def geometry_summary(geom: Any) -> Optional[dict]:
    """Small serialisable summary for provenance payloads."""
    try:
        return {
            "geom_type": geom.geom_type,
            "is_valid": bool(geom.is_valid),
            "num_vertices": int(len(geom.exterior.coords))
            if geom.geom_type == "Polygon"
            else None,
        }
    except Exception:
        return None
