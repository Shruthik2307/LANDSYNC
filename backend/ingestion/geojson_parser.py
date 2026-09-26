"""
backend/ingestion/geojson_parser.py
===================================
Production GeoJSON/JSON parser preserving full backward compatibility.
"""

from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Optional, Dict, Any, List

import geopandas as gpd
from shapely.geometry import mapping

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


class GeoJSONDocumentParser(BaseDocumentParser):
    """Parser for GeoJSON and JSON land record files."""

    def can_parse(self, file_path: Path) -> bool:
        ext = file_path.suffix.lower()
        return ext in {".geojson", ".json"}

    def parse(
        self,
        file_path: Path,
        crs_hint: Optional[str] = None,
        source_label: str = "cadastral",
        **kwargs,
    ) -> DocumentParsingResult:
        result = DocumentParsingResult(
            document_name=file_path.name,
            document_format="geojson",
            document_type="SPATIAL_VECTOR",
            target_crs="EPSG:4326",
        )

        try:
            with open(file_path, "rb") as fp:
                data = json.load(fp)
        except Exception as exc:
            result.parsing_status = ParsingStatus.FAILED
            result.errors.append(f"Invalid JSON/GeoJSON syntax: {exc}")
            return result

        if not isinstance(data, dict) or data.get("type") != "FeatureCollection":
            result.parsing_status = ParsingStatus.FAILED
            result.errors.append("Invalid GeoJSON: Root element must be of type 'FeatureCollection'.")
            return result

        features = data.get("features", [])
        if not features:
            result.parsing_status = ParsingStatus.FAILED
            result.errors.append("GeoJSON FeatureCollection contains 0 features.")
            return result

        # Check CRS
        src_crs = crs_hint or "EPSG:4326"
        if "crs" in data and isinstance(data["crs"], dict):
            crs_prop = data["crs"].get("properties", {}).get("name", "")
            if crs_prop:
                src_crs = crs_prop
                result.crs_status = CRSStatus.VALID
            else:
                result.crs_status = CRSStatus.ASSUMED_WGS84
        else:
            result.crs_status = CRSStatus.ASSUMED_WGS84

        result.source_crs = src_crs

        canonical_parcels: List[CanonicalParcel] = []
        valid_geom_count = 0

        for idx, feat in enumerate(features):
            props = feat.get("properties") or {}
            raw_geom = feat.get("geometry")

            # Determine parcel ID
            pid = (
                props.get("parcel_id")
                or props.get("PARCEL_ID")
                or props.get("id")
                or props.get("ID")
                or props.get("survey_no")
                or props.get("SURVEY_NO")
                or props.get("Base_Syno")
                or props.get("OLD_SNO")
                or f"{source_label}-{idx + 1}"
            )
            pid = str(pid).strip()

            survey_num = (
                props.get("survey_number")
                or props.get("survey_no")
                or props.get("SURVEY_NO")
                or props.get("sno")
                or props.get("OLD_SNO")
                or pid
            )

            # Repair and validate geometry
            repaired_geom = self.repair_geometry(raw_geom)
            if repaired_geom and src_crs.upper() != "EPSG:4326":
                repaired_geom = self.reproject_geometry(repaired_geom, src_crs, "EPSG:4326")

            geom_status = GeometryStatus.VALID_POLYGONS if repaired_geom else GeometryStatus.INVALID_GEOMETRY
            if repaired_geom:
                valid_geom_count += 1

            field_conf = {
                "parcel_id": FieldConfidence(value=pid, confidence=1.0, method="DIRECT"),
                "survey_number": FieldConfidence(value=str(survey_num), confidence=1.0, method="DIRECT"),
            }

            land_use = props.get("land_use") or props.get("LAND_USE") or props.get("use")
            if land_use:
                field_conf["land_use"] = FieldConfidence(value=str(land_use), confidence=1.0, method="DIRECT")

            classification = props.get("classification") or props.get("CLASSIFICATION") or props.get("class")
            if classification:
                field_conf["classification"] = FieldConfidence(value=str(classification), confidence=1.0, method="DIRECT")

            area_val = props.get("area") or props.get("AREA") or props.get("shape_area")
            try:
                area_float = float(area_val) if area_val is not None else None
            except (ValueError, TypeError):
                area_float = None

            parcel = CanonicalParcel(
                parcel_id=pid,
                geometry=repaired_geom,
                source=source_label,
                survey_number=str(survey_num) if survey_num else None,
                land_use=str(land_use) if land_use else None,
                classification=str(classification) if classification else None,
                area=area_float,
                attributes=props,
                source_document=file_path.name,
                confidence=1.0,
                extraction_method="GEOJSON_PARSER",
                crs="EPSG:4326",
                geometry_status=geom_status,
                field_confidences=field_conf,
            )
            canonical_parcels.append(parcel)

        result.parcels = canonical_parcels
        result.has_spatial_geometry = valid_geom_count > 0
        result.parsing_status = ParsingStatus.SUCCESS if valid_geom_count > 0 else ParsingStatus.PARTIAL
        result.geometry_status = (
            GeometryStatus.VALID_POLYGONS if valid_geom_count == len(canonical_parcels)
            else GeometryStatus.METADATA_ONLY if valid_geom_count == 0
            else GeometryStatus.REPAIRED_POLYGONS
        )
        result.extraction_confidence = ExtractionConfidence(
            document_extraction_confidence=1.0,
            geometry_confidence=1.0 if valid_geom_count > 0 else 0.0,
        )
        result.metadata = {
            "feature_count": len(canonical_parcels),
            "valid_geometry_count": valid_geom_count,
        }
        return result
