"""
engine/matching.py
==================
Parcel matching between two GeoDataFrames.

Strategy (from implementation plan):
    1. Primary  — exact merge on 'parcel_id'  (O(n) hash join).
    2. Fallback — spatial bounding-box sjoin  (O(n log n) via STRtree)
                  for rows that could not be matched by ID.

Both inputs MUST already be in EPSG:3857.  Call CRSManager.reproject()
before passing data to this module.
"""

from __future__ import annotations

import warnings
from typing import Optional

import geopandas as gpd
import pandas as pd
from shapely.geometry import box

# Column that uniquely identifies a parcel in both datasets.
PARCEL_ID_COL: str = "parcel_id"

# Suffixes applied to overlapping non-key columns after the merge.
SUFFIX_A: str = "_a"
SUFFIX_B: str = "_b"

# Expected CRS — enforced at function entry.
REQUIRED_EPSG: int = 3857


def match_parcels(
    gdf_a: gpd.GeoDataFrame,
    gdf_b: gpd.GeoDataFrame,
    *,
    id_col: str = PARCEL_ID_COL,
    spatial_fallback: bool = True,
) -> gpd.GeoDataFrame:
    """Match parcels between two GeoDataFrames.

    Parameters
    ----------
    gdf_a : gpd.GeoDataFrame
        First dataset (e.g. cadastral). Must be in EPSG:3857.
    gdf_b : gpd.GeoDataFrame
        Second dataset (e.g. municipal). Must be in EPSG:3857.
    id_col : str, optional
        Column name used for the primary exact join. Default ``'parcel_id'``.
    spatial_fallback : bool, optional
        If True (default), unmatched rows are attempted via bounding-box
        spatial join. Set False to use ID-only matching.

    Returns
    -------
    gpd.GeoDataFrame
        Merged GeoDataFrame with columns suffixed ``_a`` / ``_b`` for
        all non-key overlapping columns. Geometry columns are named
        ``geometry_a`` and ``geometry_b``.
        The active geometry is set to ``geometry_a``.

    Raises
    ------
    ValueError
        If either input is not in EPSG:3857, or if *id_col* is absent
        from one of the datasets.
    """
    _assert_epsg3857(gdf_a, "gdf_a")
    _assert_epsg3857(gdf_b, "gdf_b")
    _assert_column_exists(gdf_a, id_col, "gdf_a")
    _assert_column_exists(gdf_b, id_col, "gdf_b")

    # Rename geometry columns before merging so both are preserved.
    gdf_a = gdf_a.rename_geometry("geometry_a")
    gdf_b = gdf_b.rename_geometry("geometry_b")

    # ------------------------------------------------------------------ #
    # Stage 1 — Primary exact join on parcel_id                           #
    # ------------------------------------------------------------------ #
    exact = pd.merge(
        gdf_a,
        gdf_b,
        on=id_col,
        suffixes=(SUFFIX_A, SUFFIX_B),
        how="inner",
    )

    matched_ids: set = set(exact[id_col].unique())

    if not spatial_fallback:
        return _finalise(exact, "geometry_a")

    # ------------------------------------------------------------------ #
    # Stage 2 — Spatial bounding-box fallback for unmatched rows          #
    # ------------------------------------------------------------------ #
    unmatched_a = gdf_a[~gdf_a[id_col].isin(matched_ids)].copy()
    unmatched_b = gdf_b[~gdf_b[id_col].isin(matched_ids)].copy()

    spatial_matches: Optional[pd.DataFrame] = None

    if not unmatched_a.empty and not unmatched_b.empty:
        spatial_matches = _spatial_bbox_join(
            unmatched_a, unmatched_b, id_col=id_col
        )

    # ------------------------------------------------------------------ #
    # Stage 3 — Combine & deduplicate                                     #
    # ------------------------------------------------------------------ #
    frames = [exact]
    if spatial_matches is not None and not spatial_matches.empty:
        frames.append(spatial_matches)

    combined = pd.concat(frames, ignore_index=True)
    # Return all candidates. Deduplication and winner selection
    # now happen in the pipeline using metrics.
    return _finalise(combined, "geometry_a")


# --------------------------------------------------------------------------- #
# Private helpers                                                              #
# --------------------------------------------------------------------------- #

def _spatial_bbox_join(
    unmatched_a: gpd.GeoDataFrame,
    unmatched_b: gpd.GeoDataFrame,
    *,
    id_col: str,
) -> gpd.GeoDataFrame:
    """Join unmatched rows via bounding-box (envelope) intersection.

    Uses geopandas STRtree-accelerated spatial join with
    ``predicate='intersects'`` on the envelope geometries.  This is an
    O(n log n) approximation that avoids full polygon intersection.

    Parameters
    ----------
    unmatched_a, unmatched_b : gpd.GeoDataFrame
        Rows that were not matched in the exact ID join.
    id_col : str
        The parcel ID column name.

    Returns
    -------
    gpd.GeoDataFrame
        Spatially matched rows with the same column layout as the
        exact join output.
    """
    # Work on positional indexes so sjoin results can be mapped back to the
    # source rows unambiguously (original indexes may carry non-unique labels).
    env_a = unmatched_a.copy().reset_index(drop=True)
    env_b = unmatched_b.copy().reset_index(drop=True)
    env_a["geometry_a"] = env_a["geometry_a"].envelope
    env_b["geometry_b"] = env_b["geometry_b"].envelope

    # Temporarily set active geometry for sjoin.
    env_a = env_a.set_geometry("geometry_a")
    env_b = env_b.set_geometry("geometry_b")

    try:
        joined = gpd.sjoin(
            env_a,
            env_b,
            how="inner",
            predicate="intersects",
            lsuffix="a",
            rsuffix="b",
        )
    except Exception as exc:  # pragma: no cover
        warnings.warn(
            f"Spatial fallback join failed ({exc}). "
            "Returning only exact-matched results.",
            RuntimeWarning,
            stacklevel=3,
        )
        return gpd.GeoDataFrame()

    if joined.empty:
        return gpd.GeoDataFrame()

    # sjoin renames the shared join key (parcel_id → parcel_id_a/parcel_id_b)
    # and does NOT carry the right frame's geometry column into the result.
    # Normalise the key back and restore BOTH original geometries from the
    # unmatched frames via the sjoin index columns.
    left_key = f"{id_col}_a"
    right_key = f"{id_col}_b"
    if id_col not in joined.columns:
        if left_key in joined.columns:
            joined = joined.rename(columns={left_key: id_col})
        elif right_key in joined.columns:
            joined = joined.rename(columns={right_key: id_col})
    joined = joined.drop(
        columns=[c for c in (left_key, right_key) if c in joined.columns]
    )

    # Left rows: the result index holds env_a's positional index.
    joined["geometry_a"] = [env_a["geometry_a"].iloc[i] for i in joined.index]

    # Right rows: env_b's position arrives as a column whose name varies by
    # geopandas version ('index_right', 'index_b', or 'index_rightb').
    right_pos_col = next(
        (
            c
            for c in ("index_right", "index_b", "index_rightb")
            if c in joined.columns
        ),
        None,
    )
    needs_b = "geometry_b" not in joined.columns or joined["geometry_b"].isna().all()
    if right_pos_col is not None and needs_b:
        joined["geometry_b"] = [
            env_b["geometry_b"].iloc[i] for i in joined[right_pos_col]
        ]
    elif right_pos_col is not None:
        joined = joined.drop(columns=[right_pos_col])

    joined = joined.reset_index(drop=True)

    return gpd.GeoDataFrame(joined, geometry="geometry_a", crs=f"EPSG:{REQUIRED_EPSG}")


def _assert_epsg3857(gdf: gpd.GeoDataFrame, name: str) -> None:
    """Raise ValueError if *gdf* is not in EPSG:3857."""
    if not isinstance(gdf, gpd.GeoDataFrame):
        raise TypeError(f"{name} must be a GeoDataFrame.")
    if gdf.crs is None or gdf.crs.to_epsg() != REQUIRED_EPSG:
        actual = gdf.crs.to_epsg() if gdf.crs else "None"
        raise ValueError(
            f"{name} must be in EPSG:{REQUIRED_EPSG} before calling "
            f"match_parcels(). Got EPSG:{actual}. "
            "Use CRSManager.reproject() first."
        )


def _assert_column_exists(
    gdf: gpd.GeoDataFrame, col: str, name: str
) -> None:
    """Raise ValueError if *col* is missing from *gdf*."""
    if col not in gdf.columns:
        raise ValueError(
            f"Column {col!r} not found in {name}. "
            f"Available columns: {list(gdf.columns)}"
        )


def _finalise(df: pd.DataFrame, active_geom: str) -> gpd.GeoDataFrame:
    """Promote *df* to a GeoDataFrame with *active_geom* as geometry."""
    if active_geom not in df.columns:
        # Edge case: empty result with no geometry column.
        return gpd.GeoDataFrame(df, crs=f"EPSG:{REQUIRED_EPSG}")
    return gpd.GeoDataFrame(
        df, geometry=active_geom, crs=f"EPSG:{REQUIRED_EPSG}"
    )
