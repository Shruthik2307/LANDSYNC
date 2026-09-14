"""
engine/crs.py
=============
CRS normalisation utilities.

Rule (from .agentrules):
    Always normalise coordinate systems to EPSG:3857 before measuring
    metric area. All spatial measurements must use EPSG:3857.
"""

from __future__ import annotations

import geopandas as gpd

# Target projection — Web Mercator (metric, unit = metres).
TARGET_EPSG: int = 3857
TARGET_CRS: str = f"EPSG:{TARGET_EPSG}"


class CRSManager:
    """Reprojects GeoDataFrames to EPSG:3857 before any spatial operation.

    Usage
    -----
    >>> from engine.crs import CRSManager
    >>> gdf_metric = CRSManager.reproject(gdf)

    All returned GeoDataFrames are guaranteed to be in EPSG:3857.
    """

    @staticmethod
    def reproject(gdf: gpd.GeoDataFrame) -> gpd.GeoDataFrame:
        """Reproject *gdf* to EPSG:3857.

        Parameters
        ----------
        gdf : gpd.GeoDataFrame
            Input GeoDataFrame in any CRS.

        Returns
        -------
        gpd.GeoDataFrame
            A new GeoDataFrame (or the original if already EPSG:3857)
            whose CRS is guaranteed to be EPSG:3857.

        Raises
        ------
        TypeError
            If *gdf* is not a GeoDataFrame.
        ValueError
            If *gdf* has no CRS defined (``gdf.crs is None``).
        """
        CRSManager._validate_type(gdf)
        CRSManager._validate_crs_defined(gdf)

        if CRSManager._is_target_crs(gdf):
            # Already in EPSG:3857 — return as-is (zero-copy no-op).
            return gdf

        reprojected = gdf.to_crs(epsg=TARGET_EPSG)
        CRSManager._validate_metric(reprojected)
        return reprojected

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _validate_type(gdf: object) -> None:
        """Raise TypeError if *gdf* is not a GeoDataFrame."""
        if not isinstance(gdf, gpd.GeoDataFrame):
            raise TypeError(
                f"Expected a GeoDataFrame, got {type(gdf).__name__!r}."
            )

    @staticmethod
    def _validate_crs_defined(gdf: gpd.GeoDataFrame) -> None:
        """Raise ValueError if the GeoDataFrame has no CRS attached."""
        if gdf.crs is None:
            raise ValueError(
                "The GeoDataFrame has no CRS defined. "
                "Set a CRS (e.g. gdf.set_crs(epsg=4326)) before calling "
                "CRSManager.reproject()."
            )

    @staticmethod
    def _is_target_crs(gdf: gpd.GeoDataFrame) -> bool:
        """Return True if *gdf* is already in EPSG:3857."""
        return gdf.crs.to_epsg() == TARGET_EPSG

    @staticmethod
    def _validate_metric(gdf: gpd.GeoDataFrame) -> None:
        """Assert that the reprojected CRS uses metre as its linear unit.

        This is a defensive check — EPSG:3857 is always metric, but we
        verify to guard against unexpected pyproj behaviour.
        """
        axis_info = gdf.crs.axis_info
        units = {ax.unit_name.lower() for ax in axis_info}
        if "metre" not in units and "meter" not in units:
            raise RuntimeError(
                f"Reprojection produced a non-metric CRS: {gdf.crs}. "
                "Expected EPSG:3857 (metres)."
            )
