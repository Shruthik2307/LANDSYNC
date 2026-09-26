"""
backend/ingestion
=================
Multi-format land document ingestion subsystem for LANDSYNC.
Supports GeoJSON, JSON, PDF (text & scanned OCR), Images (PNG/JPG/TIFF),
CAD (DXF & DWG conversion guidance), Shapefile ZIP, KML/KMZ, GeoPackage, and GeoTIFF.
"""

from .models import (
    CanonicalParcel,
    DocumentParsingResult,
    ExtractionConfidence,
    FieldConfidence,
    GeometryStatus,
    ParsingStatus,
    OCRStatus,
    CRSStatus,
)
from .router import parse_document, parse_uploaded_files, to_feature_collection

__all__ = [
    "CanonicalParcel",
    "DocumentParsingResult",
    "ExtractionConfidence",
    "FieldConfidence",
    "GeometryStatus",
    "ParsingStatus",
    "OCRStatus",
    "CRSStatus",
    "parse_document",
    "parse_uploaded_files",
    "to_feature_collection",
]
