"""
backend/ingestion/geotiff_parser.py
===================================
GeoTIFF raster survey parser. Extracts raster georeferencing, bounding extent,
and spatial coverage metadata. Honestly marks data as RASTER_SURVEY without
pretending raster grid pixels are parcel polygons.
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Optional, List, Dict, Any

from shapely.geometry import box, mapping
import rasterio

from .base import BaseDocumentParser
from .models import (
    DocumentParsingResult,
    CanonicalParcel,
    ParsingStatus,
    GeometryStatus,
    CRSStatus,
    ExtractionConfidence,
    FieldConfidence,
)

logger = logging.getLogger(__name__)


class GeoTIFFDocumentParser(BaseDocumentParser):
    """Parser for GeoTIFF raster survey images."""

    def can_parse(self, file_path: Path) -> bool:
        ext = file_path.suffix.lower()
        if ext in {".tif", ".tiff"}:
            try:
                with rasterio.open(file_path) as src:
                    if src.crs is not None:
                        return True
                    t = src.transform
                    if t and (t.a != 1.0 or t.e != 1.0 or t.c != 0.0 or t.f != 0.0):
                        return True
            except Exception:
                return False
        return False

    def parse(
        self,
        file_path: Path,
        crs_hint: Optional[str] = None,
        source_label: str = "municipal",
        **kwargs,
    ) -> DocumentParsingResult:
        result = DocumentParsingResult(
            document_name=file_path.name,
            document_format="geotiff",
            document_type="RASTER_SURVEY",
            target_crs="EPSG:4326",
        )

        try:
            with rasterio.open(file_path) as src:
                src_crs = str(src.crs) if src.crs else crs_hint
                bounds = src.bounds
                width = src.width
                height = src.height
                bands = src.count
                res = src.res

            if not src_crs:
                result.parsing_status = ParsingStatus.CRS_REQUIRED
                result.crs_status = CRSStatus.CRS_REQUIRED
                result.geometry_status = GeometryStatus.CRS_REQUIRED
                result.errors.append("GeoTIFF lacks embedded CRS georeference. CRS required for alignment.")
                return result

            result.source_crs = src_crs
            result.crs_status = CRSStatus.VALID

            # Create bounding extent polygon
            bbox_poly = box(bounds.left, bounds.bottom, bounds.right, bounds.top)
            bbox_dict = mapping(bbox_poly)

            # Reproject to EPSG:4326 if needed
            if src_crs.upper() != "EPSG:4326":
                bbox_dict = self.reproject_geometry(bbox_dict, src_crs, "EPSG:4326")

            # Honest parcel representation: this is a raster coverage bounding extent
            parcel = CanonicalParcel(
                parcel_id=f"RASTER-EXTENT-{file_path.stem}",
                geometry=bbox_dict,
                source=source_label,
                survey_number=f"SURVEY-EXTENT-{file_path.stem}",
                land_use="Aerial / Drone Raster Coverage",
                classification="Raster Survey",
                area=None,
                attributes={
                    "width_px": width,
                    "height_px": height,
                    "bands": bands,
                    "resolution": list(res),
                    "raster_bounds": list(bounds),
                    "type": "RASTER_FOOTPRINT",
                },
                source_document=file_path.name,
                confidence=0.90,
                extraction_method="GEOTIFF_METADATA",
                crs="EPSG:4326",
                geometry_status=GeometryStatus.RASTER_SURVEY,
                field_confidences={
                    "coverage": FieldConfidence(value="RASTER_SURVEY_FOOTPRINT", confidence=1.0, method="DIRECT"),
                },
            )

            result.parcels = [parcel]
            result.has_spatial_geometry = True
            result.parsing_status = ParsingStatus.SUCCESS
            result.geometry_status = GeometryStatus.RASTER_SURVEY
            result.extraction_confidence = ExtractionConfidence(
                document_extraction_confidence=1.0,
                geometry_confidence=0.90,
            )
            result.metadata = {
                "dimensions": f"{width}x{height}",
                "bands": bands,
                "resolution": res,
                "note": (
                    "GeoTIFF ingested as raster background survey. Individual parcel polygons "
                    "require cadastral vector source (GeoJSON, SHP, or DXF)."
                ),
            }

        except Exception as exc:
            result.parsing_status = ParsingStatus.FAILED
            result.errors.append(f"Failed to read GeoTIFF: {exc}")

        return result
