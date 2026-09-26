"""
backend/ingestion/shapefile_parser.py
=====================================
Shapefile ZIP parser: safely validates contents (.shp, .shx, .dbf, .prj),
preserves CRS, repairs polygons, and converts to CanonicalParcel.
"""

from __future__ import annotations

import logging
import tempfile
import shutil
from pathlib import Path
from typing import Optional, List

import geopandas as gpd
from shapely.geometry import mapping

from .base import BaseDocumentParser
from .validation import validate_and_extract_safe_zip
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


class ShapefileDocumentParser(BaseDocumentParser):
    """Parser for ESRI Shapefiles provided in .zip archives."""

    def can_parse(self, file_path: Path) -> bool:
        ext = file_path.suffix.lower()
        if ext not in {".zip", ".shp"}:
            return False
        if ext == ".shp":
            return True
        # Check if zip contains .shp
        try:
            import zipfile
            if zipfile.is_zipfile(file_path):
                with zipfile.ZipFile(file_path, "r") as zf:
                    return any(name.lower().endswith(".shp") for name in zf.namelist())
        except Exception:
            return False
        return False

    def parse(
        self,
        file_path: Path,
        crs_hint: Optional[str] = None,
        source_label: str = "cadastral",
        **kwargs,
    ) -> DocumentParsingResult:
        result = DocumentParsingResult(
            document_name=file_path.name,
            document_format="shapefile",
            document_type="SPATIAL_VECTOR",
            target_crs="EPSG:4326",
        )

        temp_dir = Path(tempfile.mkdtemp(prefix="landsync_shp_"))
        try:
            shp_path: Optional[Path] = None

            if file_path.suffix.lower() == ".zip":
                # Safe extraction with ZipSlip & archive bomb protections
                extracted = validate_and_extract_safe_zip(
                    file_path,
                    temp_dir,
                    required_extensions={".shp", ".dbf", ".shx"},
                )
                for p in extracted:
                    if p.suffix.lower() == ".shp":
                        shp_path = p
                        break
            else:
                shp_path = file_path

            if not shp_path or not shp_path.exists():
                result.parsing_status = ParsingStatus.FAILED
                result.errors.append("No valid .shp file found in uploaded archive.")
                return result

            # Check for PRJ
            prj_path = shp_path.with_suffix(".prj")
            has_prj = prj_path.exists() and prj_path.stat().st_size > 0

            try:
                gdf = gpd.read_file(shp_path)
            except Exception as exc:
                result.parsing_status = ParsingStatus.FAILED
                result.errors.append(f"Failed to read Shapefile: {exc}")
                return result

            if gdf.empty:
                result.parsing_status = ParsingStatus.FAILED
                result.errors.append("Shapefile contains 0 features.")
                return result

            # Handle CRS
            source_crs_str: Optional[str] = None
            if gdf.crs is not None:
                source_crs_str = str(gdf.crs)
                result.crs_status = CRSStatus.VALID
            elif has_prj:
                with open(prj_path, "r", encoding="utf-8", errors="ignore") as f:
                    source_crs_str = f.read().strip()
                result.crs_status = CRSStatus.VALID
            elif crs_hint:
                source_crs_str = crs_hint
                result.crs_status = CRSStatus.VALID
                gdf = gdf.set_crs(crs_hint)
            else:
                # Shapefiles require CRS metadata for accurate cadastral alignment
                result.crs_status = CRSStatus.CRS_REQUIRED
                result.parsing_status = ParsingStatus.CRS_REQUIRED
                result.errors.append(
                    "CRS metadata (.prj) is missing. Shapefile coordinate reference system required for geospatial reconciliation."
                )
                result.metadata = {"feature_count": len(gdf)}
                return result

            result.source_crs = source_crs_str

            # Reproject to EPSG:4326 if needed
            if gdf.crs is not None and gdf.crs.to_string() != "EPSG:4326":
                try:
                    gdf = gdf.to_crs(epsg=4326)
                except Exception as exc:
                    logger.warning("[shapefile_parser] Failed to reproject to EPSG:4326: %s", exc)
                    result.warnings.append(f"Failed to reproject from {source_crs_str} to EPSG:4326: {exc}")

            canonical_parcels: List[CanonicalParcel] = []
            valid_geom_count = 0

            for idx, row in gdf.iterrows():
                props = {k: v for k, v in row.items() if k != gdf.geometry.name}
                geom = row.geometry

                # Determine parcel_id
                pid = (
                    props.get("parcel_id")
                    or props.get("PARCEL_ID")
                    or props.get("OLD_SNO")
                    or props.get("TS_NO")
                    or props.get("survey_no")
                    or props.get("Base_Syno")
                    or props.get("OBJECTID")
                    or props.get("FID")
                    or f"{source_label}-{idx + 1}"
                )
                pid = str(pid).strip()

                survey_num = (
                    props.get("survey_number")
                    or props.get("survey_no")
                    or props.get("OLD_SNO")
                    or props.get("TS_NO")
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
                        land_use=str(props.get("land_use") or props.get("LAND_USE") or "Unknown"),
                        classification=str(props.get("class") or props.get("classification") or "Unclassified"),
                        area=float(props.get("area") or props.get("AREA") or 0.0),
                        attributes={str(k): (str(v) if v is not None else "") for k, v in props.items()},
                        source_document=file_path.name,
                        confidence=0.98,
                        extraction_method="SHAPEFILE_PARSER",
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
            result.metadata = {
                "feature_count": len(canonical_parcels),
                "valid_geometry_count": valid_geom_count,
                "detected_crs": source_crs_str,
            }

        finally:
            shutil.rmtree(temp_dir, ignore_errors=True)

        return result
