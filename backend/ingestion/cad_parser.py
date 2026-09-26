"""
backend/ingestion/cad_parser.py
===============================
CAD parser supporting DXF vector entity extraction (LINE, POLYLINE, LWPOLYLINE)
into closed polygon parcel boundaries, with honest DWG conversion guidance,
geometry repair, and strict CRS verification.
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Optional, List, Dict, Any, Tuple

import shapely.geometry
from shapely.geometry import Polygon, MultiPolygon, LineString, mapping
from shapely.ops import polygonize, unary_union

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


class CADDocumentParser(BaseDocumentParser):
    """Parser for CAD drawings (DXF) and converter advisor for DWG files."""

    def can_parse(self, file_path: Path) -> bool:
        ext = file_path.suffix.lower()
        if ext in {".dxf", ".dwg"}:
            return True
        try:
            with open(file_path, "rb") as f:
                header = f.read(16)
                if header.startswith(b"AC10"):  # DWG
                    return True
                if b"SECTION" in header or b"HEADER" in header:  # DXF
                    return True
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
        ext = file_path.suffix.lower()

        # Handle DWG
        with open(file_path, "rb") as f:
            header = f.read(16)

        if ext == ".dwg" or header.startswith(b"AC10"):
            return DocumentParsingResult(
                document_name=file_path.name,
                document_format="dwg",
                document_type="CAD_DRAWING",
                parsing_status=ParsingStatus.UNSUPPORTED_FORMAT,
                geometry_status=GeometryStatus.GEOMETRY_EXTRACTION_REQUIRED,
                crs_status=CRSStatus.NOT_APPLICABLE,
                errors=[
                    "DWG is an Autodesk proprietary binary format without a certified open-source parser. "
                    "Please convert your drawing to DXF (AutoCAD R2018/R2013 ASCII format) using LibreCAD or AutoCAD, "
                    "then re-upload to LANDSYNC for automated parcel boundary extraction."
                ],
                warnings=["DWG direct parsing unavailable in open-source runtime."],
            )

        # Parse DXF using ezdxf
        result = DocumentParsingResult(
            document_name=file_path.name,
            document_format="dxf",
            document_type="CAD_DRAWING",
            target_crs="EPSG:4326",
        )

        try:
            import ezdxf
        except ImportError:
            result.parsing_status = ParsingStatus.FAILED
            result.errors.append("ezdxf CAD library is not installed in runtime.")
            return result

        try:
            doc = ezdxf.readfile(str(file_path))
            msp = doc.modelspace()
        except Exception as exc:
            result.parsing_status = ParsingStatus.FAILED
            result.errors.append(f"Failed to read DXF file: {exc}")
            return result

        # Extract text annotations to associate survey numbers with nearby polygons
        annotations: List[Tuple[float, float, str]] = []
        for text_entity in msp.query("TEXT MTEXT"):
            try:
                txt = text_entity.dxf.text if hasattr(text_entity.dxf, "text") else ""
                if not txt and hasattr(text_entity, "text"):
                    txt = text_entity.text
                pt = text_entity.dxf.insert if hasattr(text_entity.dxf, "insert") else None
                if txt and pt:
                    annotations.append((pt.x, pt.y, str(txt).strip()))
            except Exception:
                continue

        # Extract lines and polylines
        candidate_lines: List[LineString] = []
        closed_polygons: List[Polygon] = []

        # 1. LWPOLYLINE entities
        for lw in msp.query("LWPOLYLINE"):
            try:
                pts = [(p[0], p[1]) for p in lw.get_points(format="xy")]
                if len(pts) >= 3:
                    if lw.is_closed or pts[0] == pts[-1]:
                        if pts[0] != pts[-1]:
                            pts.append(pts[0])
                        p_poly = Polygon(pts)
                        if p_poly.is_valid and p_poly.area > 0:
                            closed_polygons.append(p_poly)
                    else:
                        candidate_lines.append(LineString(pts))
            except Exception:
                continue

        # 2. 2D/3D POLYLINE entities
        for pl in msp.query("POLYLINE"):
            try:
                pts = [(v.dxf.location.x, v.dxf.location.y) for v in pl.vertices]
                if len(pts) >= 3:
                    if pl.is_closed or pts[0] == pts[-1]:
                        if pts[0] != pts[-1]:
                            pts.append(pts[0])
                        p_poly = Polygon(pts)
                        if p_poly.is_valid and p_poly.area > 0:
                            closed_polygons.append(p_poly)
                    else:
                        candidate_lines.append(LineString(pts))
            except Exception:
                continue

        # 3. LINE entities
        for l in msp.query("LINE"):
            try:
                st = l.dxf.start
                en = l.dxf.end
                candidate_lines.append(LineString([(st.x, st.y), (en.x, en.y)]))
            except Exception:
                continue

        # If lines exist, assemble them into polygons via polygonize
        if candidate_lines:
            try:
                merged_lines = unary_union(candidate_lines)
                built_polys = list(polygonize(merged_lines))
                for bp in built_polys:
                    if bp.is_valid and bp.area > 0:
                        closed_polygons.append(bp)
            except Exception as exc:
                logger.warning("[cad_parser] Line polygonization warning: %s", exc)

        if not closed_polygons:
            result.parsing_status = ParsingStatus.PARTIAL
            result.geometry_status = GeometryStatus.METADATA_ONLY
            result.errors.append("No closed boundary polygons could be reconstructed from CAD entities.")
            result.metadata = {
                "entity_count": len(msp),
                "text_annotations_found": len(annotations),
            }
            return result

        # Check Coordinates / CRS
        # Inspect coordinate ranges across all extracted polygons
        min_x = min(p.bounds[0] for p in closed_polygons)
        min_y = min(p.bounds[1] for p in closed_polygons)
        max_x = max(p.bounds[2] for p in closed_polygons)
        max_y = max(p.bounds[3] for p in closed_polygons)

        # Are coordinates already geographic degrees (WGS84)?
        is_geographic = (-180.0 <= min_x <= 180.0 and -90.0 <= min_y <= 90.0 and
                         -180.0 <= max_x <= 180.0 and -90.0 <= max_y <= 90.0)

        source_crs = crs_hint
        if not source_crs:
            if is_geographic:
                source_crs = "EPSG:4326"
                result.crs_status = CRSStatus.ASSUMED_WGS84
            else:
                # CAD files with local or UTM metric coordinates MUST have explicit CRS
                result.parsing_status = ParsingStatus.CRS_REQUIRED
                result.crs_status = CRSStatus.CRS_REQUIRED
                result.geometry_status = GeometryStatus.CRS_REQUIRED
                result.errors.append(
                    f"CRS required: CAD coordinates ({min_x:.1f}, {min_y:.1f}) are in local or projected units. "
                    "Specify CRS metadata (e.g., EPSG:32644 for Telangana UTM Zone 44N) to allow geospatial alignment."
                )
                result.metadata = {
                    "polygons_detected": len(closed_polygons),
                    "coordinate_bounds": [min_x, min_y, max_x, max_y],
                }
                return result

        result.source_crs = source_crs

        # Transform to EPSG:4326 if not already
        canonical_parcels: List[CanonicalParcel] = []
        valid_geom_count = 0

        for idx, poly in enumerate(closed_polygons):
            repaired_geom = self.repair_geometry(poly)
            if repaired_geom and source_crs.upper() != "EPSG:4326":
                repaired_geom = self.reproject_geometry(repaired_geom, source_crs, "EPSG:4326")

            if repaired_geom:
                valid_geom_count += 1

            # Match nearest text annotation for survey number
            survey_no = f"{source_label}-{idx + 1}"
            center = poly.centroid
            best_dist = float("inf")
            for ax, ay, atxt in annotations:
                dist = ((center.x - ax) ** 2 + (center.y - ay) ** 2) ** 0.5
                if dist < best_dist and dist < poly.length:  # reasonably close
                    best_dist = dist
                    survey_no = atxt

            pid = survey_no if survey_no != f"{source_label}-{idx + 1}" else f"CAD-{idx + 1}"

            geom_status = GeometryStatus.VALID_POLYGONS if repaired_geom else GeometryStatus.INVALID_GEOMETRY

            canonical_parcels.append(
                CanonicalParcel(
                    parcel_id=pid,
                    geometry=repaired_geom,
                    source=source_label,
                    survey_number=survey_no,
                    land_use="Unknown",
                    classification="Cadastral Boundary",
                    area=round(float(poly.area), 2),
                    attributes={"source_layer": "CAD_MODELSPACE", "dxf_type": "VECTOR_PARCEL"},
                    source_document=file_path.name,
                    confidence=0.92,
                    extraction_method="CAD_VECTOR_EXTRACTION",
                    crs="EPSG:4326",
                    geometry_status=geom_status,
                    field_confidences={
                        "parcel_id": FieldConfidence(value=pid, confidence=0.92, method="CAD_ATTRIBUTE"),
                        "survey_number": FieldConfidence(value=survey_no, confidence=0.90, method="CAD_ATTRIBUTE"),
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
            document_extraction_confidence=0.95,
            geometry_confidence=0.92 if valid_geom_count > 0 else 0.0,
        )
        result.metadata = {
            "polygons_detected": len(closed_polygons),
            "valid_geometry_count": valid_geom_count,
            "text_annotations_count": len(annotations),
            "source_crs": source_crs,
        }

        return result
