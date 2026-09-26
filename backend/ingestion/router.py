"""
backend/ingestion/router.py
===========================
Unified ingestion router: dispatches incoming files to the appropriate parser,
normalises results to CanonicalParcel instances, and exports GeoJSON FeatureCollections
for backward-compatible engine reconciliation.
"""

from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import List, Optional, Dict, Any

from .models import (
    CanonicalParcel,
    DocumentParsingResult,
    ParsingStatus,
    GeometryStatus,
    CRSStatus,
)
from .validation import detect_file_type, validate_file_size
from .geojson_parser import GeoJSONDocumentParser
from .shapefile_parser import ShapefileDocumentParser
from .kml_parser import KMLDocumentParser
from .geopackage_parser import GeoPackageDocumentParser
from .cad_parser import CADDocumentParser
from .pdf_parser import PDFDocumentParser
from .image_parser import ImageDocumentParser
from .geotiff_parser import GeoTIFFDocumentParser

logger = logging.getLogger(__name__)

# Registered parser instances
_PARSERS = [
    GeoJSONDocumentParser(),
    ShapefileDocumentParser(),
    KMLDocumentParser(),
    GeoPackageDocumentParser(),
    CADDocumentParser(),
    PDFDocumentParser(),
    GeoTIFFDocumentParser(),
    ImageDocumentParser(),
]


def get_parser_for_file(file_path: Path):
    """Find the best parser for the specified file."""
    for parser in _PARSERS:
        if parser.can_parse(file_path):
            return parser
    return None


def parse_document(
    file_path: Path,
    crs_hint: Optional[str] = None,
    source_label: str = "cadastral",
    **kwargs,
) -> DocumentParsingResult:
    """Parse any supported land document file into a DocumentParsingResult."""
    # 1. Validate file size and basic existence
    if not file_path.exists():
        return DocumentParsingResult(
            document_name=file_path.name,
            document_format=file_path.suffix.lstrip(".").lower(),
            document_type="UNKNOWN",
            parsing_status=ParsingStatus.FAILED,
            errors=[f"File not found: {file_path.name}"],
        )

    try:
        validate_file_size(file_path)
    except Exception as exc:
        return DocumentParsingResult(
            document_name=file_path.name,
            document_format=file_path.suffix.lstrip(".").lower(),
            document_type="UNKNOWN",
            parsing_status=ParsingStatus.FAILED,
            errors=[str(exc)],
        )

    # 2. Match parser
    parser = get_parser_for_file(file_path)
    if not parser:
        detected_type, _ = detect_file_type(file_path)
        return DocumentParsingResult(
            document_name=file_path.name,
            document_format=detected_type,
            document_type="UNSUPPORTED",
            parsing_status=ParsingStatus.UNSUPPORTED_FORMAT,
            geometry_status=GeometryStatus.METADATA_ONLY,
            crs_status=CRSStatus.NOT_APPLICABLE,
            errors=[f"Unsupported file format: {file_path.suffix!r}."],
        )

    # 3. Parse
    try:
        return parser.parse(file_path, crs_hint=crs_hint, source_label=source_label, **kwargs)
    except Exception as exc:
        logger.error("[router] Unexpected exception in %s for %s: %s", parser.__class__.__name__, file_path.name, exc, exc_info=True)
        return DocumentParsingResult(
            document_name=file_path.name,
            document_format=file_path.suffix.lstrip(".").lower(),
            document_type="UNKNOWN",
            parsing_status=ParsingStatus.FAILED,
            errors=[f"Internal parsing exception: {exc}"],
        )


def parse_uploaded_files(
    file_paths: List[Path],
    crs_hints: Optional[Dict[str, str]] = None,
) -> List[DocumentParsingResult]:
    """Parse multiple uploaded files with smart cadastral/municipal assignment."""
    results: List[DocumentParsingResult] = []
    cadastral_clues = ("cadastr", "revenue", "ror", "khasra", "deed", "land_record", "rev")
    municipal_clues = ("municip", "survey", "ulb", "drone", "town", "ghmc", "mun")

    hints = crs_hints or {}

    for idx, path in enumerate(file_paths):
        name_lower = path.name.lower()
        if any(c in name_lower for c in cadastral_clues):
            label = "cadastral"
        elif any(m in name_lower for m in municipal_clues):
            label = "municipal"
        else:
            # Assign first file as cadastral, second as municipal
            label = "cadastral" if idx == 0 else "municipal"

        hint = hints.get(path.name) or hints.get(str(path))
        res = parse_document(path, crs_hint=hint, source_label=label)
        results.append(res)

    return results


def to_feature_collection(parcels: List[CanonicalParcel]) -> Dict[str, Any]:
    """Convert a list of CanonicalParcels to a GeoJSON FeatureCollection."""
    features = [
        p.to_geojson_feature() for p in parcels
        if p.geometry is not None
    ]
    return {
        "type": "FeatureCollection",
        "crs": {
            "type": "name",
            "properties": {"name": "urn:ogc:def:crs:OGC:1.3:CRS84"},
        },
        "features": features,
    }


def sync_to_geojson_cache(
    dataset_id: str,
    parsing_results: List[DocumentParsingResult],
    target_dir: Path,
) -> List[Path]:
    """Convert parsed spatial parcels into GeoJSON FeatureCollections in target_dir.

    Ensures seamless backward-compatibility: any vector format (Shapefile,
    DXF, KML, GPKG) becomes available as a validated GeoJSON dataset
    for the existing reconciliation engine.
    """
    target_dir.mkdir(parents=True, exist_ok=True)
    generated_paths: List[Path] = []

    for idx, res in enumerate(parsing_results):
        if res.document_format == "geojson":
            continue
        spatial_parcels = [p for p in res.parcels if p.geometry is not None]
        if spatial_parcels:
            fc = to_feature_collection(spatial_parcels)
            stem = Path(res.document_name).stem
            # Save normalized geojson
            out_path = target_dir / f"{dataset_id}_{stem}.geojson"
            with open(out_path, "w", encoding="utf-8") as f:
                json.dump(fc, f, indent=2)
            generated_paths.append(out_path)

    return generated_paths
