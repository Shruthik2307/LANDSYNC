"""
backend/ingestion/models.py
===========================
Canonical representations and confidence scoring models for multi-format
land-record ingestion.
"""

from __future__ import annotations

from enum import Enum
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field


class ParsingStatus(str, Enum):
    SUCCESS = "SUCCESS"
    PARTIAL = "PARTIAL"
    CRS_REQUIRED = "CRS_REQUIRED"
    GEOMETRY_EXTRACTION_REQUIRED = "GEOMETRY_EXTRACTION_REQUIRED"
    UNSUPPORTED_FORMAT = "UNSUPPORTED_FORMAT"
    FAILED = "FAILED"


class OCRStatus(str, Enum):
    NOT_APPLICABLE = "NOT_APPLICABLE"
    COMPLETED = "COMPLETED"
    UNAVAILABLE = "UNAVAILABLE"
    LOW_CONFIDENCE = "LOW_CONFIDENCE"


class GeometryStatus(str, Enum):
    VALID_POLYGONS = "VALID_POLYGONS"
    REPAIRED_POLYGONS = "REPAIRED_POLYGONS"
    CRS_REQUIRED = "CRS_REQUIRED"
    METADATA_ONLY = "METADATA_ONLY"
    GEOMETRY_EXTRACTION_REQUIRED = "GEOMETRY_EXTRACTION_REQUIRED"
    RASTER_SURVEY = "RASTER_SURVEY"
    INVALID_GEOMETRY = "INVALID_GEOMETRY"


class CRSStatus(str, Enum):
    VALID = "VALID"
    ASSUMED_WGS84 = "ASSUMED_WGS84"
    CRS_REQUIRED = "CRS_REQUIRED"
    NOT_APPLICABLE = "NOT_APPLICABLE"


class FieldConfidence(BaseModel):
    """Retains value, confidence score, and extraction method for individual fields."""
    value: Any
    confidence: float = Field(default=1.0, ge=0.0, le=1.0)
    method: str = Field(default="DIRECT")  # e.g., "DIRECT", "PARSED", "OCR", "CAD_ATTRIBUTE", "DEFAULT"


class ExtractionConfidence(BaseModel):
    """Separate confidence layers for multi-format ingestion (Phase 10).

    Does NOT combine disparate metrics into one arbitrary number unless
    mathematically justified.
    """
    document_extraction_confidence: float = Field(default=1.0, ge=0.0, le=1.0)
    geometry_confidence: float = Field(default=1.0, ge=0.0, le=1.0)
    parcel_matching_confidence: Optional[float] = Field(default=None, ge=0.0, le=1.0)
    ml_prediction_confidence: Optional[float] = Field(default=None, ge=0.0, le=1.0)
    final_reconciliation_confidence: Optional[float] = Field(default=None, ge=0.0, le=1.0)


class CanonicalParcel(BaseModel):
    """Standardized representation of an ingested parcel across all file formats."""
    parcel_id: str
    geometry: Optional[Dict[str, Any]] = None  # GeoJSON geometry dict (Polygon / MultiPolygon)
    source: str = "cadastral"  # "cadastral" | "municipal" | "revenue" | "deed"
    survey_number: Optional[str] = None
    land_use: Optional[str] = None
    classification: Optional[str] = None
    area: Optional[float] = None
    attributes: Dict[str, Any] = Field(default_factory=dict)
    source_document: str = ""
    confidence: float = Field(default=1.0, ge=0.0, le=1.0)
    extraction_method: str = "PARSED"
    crs: Optional[str] = "EPSG:4326"
    geometry_status: GeometryStatus = GeometryStatus.VALID_POLYGONS
    field_confidences: Dict[str, FieldConfidence] = Field(default_factory=dict)

    def to_geojson_feature(self) -> Dict[str, Any]:
        """Convert to GeoJSON Feature with properties."""
        props = {
            "parcel_id": self.parcel_id,
            "survey_number": self.survey_number or self.parcel_id,
            "land_use": self.land_use or "Unknown",
            "classification": self.classification or "Unclassified",
            "area": self.area or 0.0,
            "source": self.source,
            "source_document": self.source_document,
            "extraction_method": self.extraction_method,
            "extraction_confidence": self.confidence,
            "geometry_status": self.geometry_status.value,
            **self.attributes,
        }
        return {
            "type": "Feature",
            "geometry": self.geometry,
            "properties": props,
        }


class DocumentParsingResult(BaseModel):
    """Complete summary and payload returned by any document parser."""
    document_name: str
    document_format: str  # "geojson", "pdf", "image", "dxf", "shapefile", "kml", "geopackage", "geotiff"
    document_type: str    # "SPATIAL_VECTOR", "TEXT_DOCUMENT", "SCANNED_IMAGE", "CAD_DRAWING", "RASTER_SURVEY"
    parcels: List[CanonicalParcel] = Field(default_factory=list)
    parsing_status: ParsingStatus = ParsingStatus.SUCCESS
    ocr_status: OCRStatus = OCRStatus.NOT_APPLICABLE
    geometry_status: GeometryStatus = GeometryStatus.VALID_POLYGONS
    crs_status: CRSStatus = CRSStatus.VALID
    source_crs: Optional[str] = None
    target_crs: str = "EPSG:4326"
    extraction_confidence: ExtractionConfidence = Field(default_factory=ExtractionConfidence)
    errors: List[str] = Field(default_factory=list)
    warnings: List[str] = Field(default_factory=list)
    metadata: Dict[str, Any] = Field(default_factory=dict)
    has_spatial_geometry: bool = False
