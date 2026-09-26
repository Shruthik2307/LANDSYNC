"""
backend/ingestion/base.py
=========================
Abstract base class for all document format parsers in LANDSYNC.
"""

from __future__ import annotations

import logging
from abc import ABC, abstractmethod
from pathlib import Path
from typing import Optional, Dict, Any, List

import shapely.geometry
from shapely.validation import make_valid
from shapely.ops import transform
import pyproj

from .models import (
    DocumentParsingResult,
    CanonicalParcel,
    ParsingStatus,
    GeometryStatus,
    CRSStatus,
    ExtractionConfidence,
)

logger = logging.getLogger(__name__)


class BaseDocumentParser(ABC):
    """Abstract base class for format-specific land document parsers."""

    @abstractmethod
    def can_parse(self, file_path: Path) -> bool:
        """Check if this parser can handle the given file."""
        pass

    @abstractmethod
    def parse(
        self,
        file_path: Path,
        crs_hint: Optional[str] = None,
        source_label: str = "cadastral",
        **kwargs,
    ) -> DocumentParsingResult:
        """Parse the input document and return a DocumentParsingResult."""
        pass

    @staticmethod
    def repair_geometry(geom: Any) -> Optional[Dict[str, Any]]:
        """Validate and repair Shapely geometry, converting into a GeoJSON mapping.

        Handles invalid geometries, self-intersections, and collapses.
        """
        if geom is None:
            return None

        # Convert to shapely if needed
        if isinstance(geom, dict):
            try:
                s_geom = shapely.geometry.shape(geom)
            except Exception:
                return None
        else:
            s_geom = geom

        if s_geom.is_empty:
            return None

        if not s_geom.is_valid:
            try:
                s_geom = make_valid(s_geom)
            except Exception as exc:
                logger.warning("[parser] Failed to make geometry valid: %s", exc)
                return None

        # Ensure we have Polygon or MultiPolygon
        if s_geom.geom_type in ("Polygon", "MultiPolygon"):
            return shapely.geometry.mapping(s_geom)
        elif s_geom.geom_type == "GeometryCollection":
            polys = [g for g in s_geom.geoms if g.geom_type in ("Polygon", "MultiPolygon")]
            if polys:
                if len(polys) == 1:
                    return shapely.geometry.mapping(polys[0])
                return shapely.geometry.mapping(shapely.geometry.MultiPolygon(polys))
        return None

    @staticmethod
    def reproject_geometry(
        geom_dict: Dict[str, Any],
        src_crs: str,
        dst_crs: str = "EPSG:4326",
    ) -> Optional[Dict[str, Any]]:
        """Transform geometry coordinates from src_crs to dst_crs."""
        if not src_crs or src_crs.upper() == dst_crs.upper():
            return geom_dict

        try:
            transformer = pyproj.Transformer.from_crs(src_crs, dst_crs, always_xy=True)
            s_geom = shapely.geometry.shape(geom_dict)
            transformed = transform(transformer.transform, s_geom)
            if not transformed.is_valid:
                transformed = make_valid(transformed)
            return shapely.geometry.mapping(transformed)
        except Exception as exc:
            logger.error("[parser] Reprojection error from %s to %s: %s", src_crs, dst_crs, exc)
            return None
