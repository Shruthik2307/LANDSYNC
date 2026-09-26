"""
backend/ingestion/geopackage_parser.py
======================================
GeoPackage (.gpkg) parser: inspects layers, extracts vector parcel polygons,
normalises CRS to EPSG:4326, and maps to CanonicalParcel.
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Optional, List, Dict, Any

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


class GeoPackageDocumentParser(BaseDocumentParser):
    """Parser for OGC GeoPackage (.gpkg) files."""

    def can_parse(self, file_path: Path) -> bool:
        ext = file_path.suffix.lower()
        if ext == ".gpkg":
            return True
        try:
            with open(file_path, "rb") as f:
                header = f.read(16)
                return header.startswith(b"SQLite format 3")
        except Exception:
            return False

    def parse(
        self,
        file_path: Path,
        crs_hint: Optional[str] = None,
        source_label: str = "cadastral",
        layer_name: Optional[str] = None,
        **kwargs,
    ) -> DocumentParsingResult:
        result = DocumentParsingResult(
            document_name=file_path.name,
            document_format="geopackage",
            document_type="SPATIAL_VECTOR",
            target_crs="EPSG:4326",
        )

        try:
            import pyogrio
            layers = pyogrio.list_layers(file_path)
            if hasattr(layers, "ndim") and layers.ndim == 2:
                layer_names = [str(layers[i, 0]) for i in range(layers.shape[0])]
            elif hasattr(layers, "__iter__"):
                layer_names = [str(l[0]) if (isinstance(l, (list, tuple)) or (hasattr(l, "__getitem__") and not isinstance(l, str))) else str(l) for l in layers]
            else:
                layer_names = []
        except Exception:
            try:
                import fiona
                layer_names = fiona.listlayers(str(file_path))
            except Exception as exc:
                result.parsing_status = ParsingStatus.FAILED
                result.errors.append(f"Failed to inspect GeoPackage layers: {exc}")
                return result

        if not layer_names:
            result.parsing_status = ParsingStatus.FAILED
            result.errors.append("GeoPackage contains no vector layers.")
            return result

        # Select target layer
        selected_layer = layer_name or layer_names[0]
        # Prefer layer with 'cadastr', 'parcel', 'boundary', or 'survey' in name if not specified
        if not layer_name and len(layer_names) > 1:
            for l in layer_names:
                l_lower = l.lower()
                if any(w in l_lower for w in ("cadastr", "parcel", "survey", "boundary", "land")):
                    selected_layer = l
                    break

        result.metadata["available_layers"] = layer_names
        result.metadata["selected_layer"] = selected_layer

        try:
            gdf = gpd.read_file(file_path, layer=selected_layer)
        except Exception as exc:
            result.parsing_status = ParsingStatus.FAILED
            result.errors.append(f"Failed to read layer '{selected_layer}' in GeoPackage: {exc}")
            return result

        if gdf.empty:
            result.parsing_status = ParsingStatus.FAILED
            result.errors.append(f"Layer '{selected_layer}' in GeoPackage contains 0 features.")
            return result

        if gdf.crs is not None:
            result.source_crs = str(gdf.crs)
            result.crs_status = CRSStatus.VALID
            if gdf.crs.to_string() != "EPSG:4326":
                try:
                    gdf = gdf.to_crs(epsg=4326)
                except Exception as exc:
                    result.warnings.append(f"Could not reproject GeoPackage to EPSG:4326: {exc}")
        elif crs_hint:
            result.source_crs = crs_hint
            result.crs_status = CRSStatus.VALID
            gdf = gdf.set_crs(crs_hint).to_crs(epsg=4326)
        else:
            result.crs_status = CRSStatus.ASSUMED_WGS84
            gdf = gdf.set_crs(epsg=4326)

        canonical_parcels: List[CanonicalParcel] = []
        valid_geom_count = 0

        for idx, row in gdf.iterrows():
            props = {k: v for k, v in row.items() if k != gdf.geometry.name}
            geom = row.geometry

            pid = (
                props.get("parcel_id")
                or props.get("PARCEL_ID")
                or props.get("survey_no")
                or props.get("fid")
                or props.get("id")
                or f"{source_label}-{idx + 1}"
            )
            pid = str(pid).strip()

            survey_num = (
                props.get("survey_number")
                or props.get("survey_no")
                or props.get("OLD_SNO")
                or pid
            )

            repaired = self.repair_geometry(geom)
            if repaired:
                valid_geom_count += 1

            geom_status = GeometryStatus.VALID_POLYGONS if repaired else GeometryStatus.INVALID_GEOMETRY

            canonical_parcels.append(
                CanonicalParcel(
                    parcel_id=pid,
                    geometry=repaired,
                    source=source_label,
                    survey_number=str(survey_num) if survey_num else None,
                    land_use=str(props.get("land_use") or "Unknown"),
                    classification=str(props.get("classification") or "Unclassified"),
                    area=float(props.get("area") or 0.0),
                    attributes={str(k): (str(v) if v is not None else "") for k, v in props.items()},
                    source_document=file_path.name,
                    confidence=0.98,
                    extraction_method="GEOPACKAGE_PARSER",
                    crs="EPSG:4326",
                    geometry_status=geom_status,
                    field_confidences={
                        "parcel_id": FieldConfidence(value=pid, confidence=1.0, method="DIRECT"),
                        "survey_number": FieldConfidence(value=str(survey_num), confidence=1.0, method="DIRECT"),
                    },
                )
            )

        result.parcels = canonical_parcels
        result.has_spatial_geometry = valid_geom_count > 0
        result.parsing_status = ParsingStatus.SUCCESS if valid_geom_count > 0 else ParsingStatus.PARTIAL
        result.geometry_status = (
            GeometryStatus.VALID_POLYGONS if valid_geom_count == len(canonical_parcels)
            else GeometryStatus.REPAIRED_POLYGONS
        )
        result.extraction_confidence = ExtractionConfidence(
            document_extraction_confidence=1.0,
            geometry_confidence=1.0 if valid_geom_count > 0 else 0.0,
        )
        result.metadata["feature_count"] = len(canonical_parcels)
        result.metadata["valid_geometry_count"] = valid_geom_count

        return result
