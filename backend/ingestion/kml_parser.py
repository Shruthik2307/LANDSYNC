"""
backend/ingestion/kml_parser.py
===============================
KML / KMZ parser extracting Placemark boundary polygons, metadata attributes,
and normalising to CanonicalParcel representations in EPSG:4326.
"""

from __future__ import annotations

import logging
import tempfile
import shutil
import xml.etree.ElementTree as ET
from pathlib import Path
from typing import Optional, List, Dict, Any

from shapely.geometry import Polygon, MultiPolygon, mapping

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


class KMLDocumentParser(BaseDocumentParser):
    """Parser for KML (Keyhole Markup Language) and KMZ (zipped KML) files."""

    def can_parse(self, file_path: Path) -> bool:
        ext = file_path.suffix.lower()
        if ext in {".kml", ".kmz"}:
            return True
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
            document_format="kml",
            document_type="SPATIAL_VECTOR",
            source_crs="EPSG:4326",
            target_crs="EPSG:4326",
            crs_status=CRSStatus.VALID,
        )

        temp_dir = Path(tempfile.mkdtemp(prefix="landsync_kml_"))
        try:
            kml_path: Optional[Path] = None

            if file_path.suffix.lower() == ".kmz":
                extracted = validate_and_extract_safe_zip(
                    file_path,
                    temp_dir,
                    required_extensions={".kml"},
                )
                for p in extracted:
                    if p.suffix.lower() == ".kml":
                        kml_path = p
                        break
            else:
                kml_path = file_path

            if not kml_path or not kml_path.exists():
                result.parsing_status = ParsingStatus.FAILED
                result.errors.append("No valid .kml content found in input file.")
                return result

            # Parse XML
            try:
                tree = ET.parse(kml_path)
                root = tree.getroot()
            except Exception as exc:
                result.parsing_status = ParsingStatus.FAILED
                result.errors.append(f"Failed to parse KML XML structure: {exc}")
                return result

            # Strip namespaces for cleaner tag querying
            for elem in root.iter():
                if "}" in elem.tag:
                    elem.tag = elem.tag.split("}", 1)[1]

            placemarks = root.findall(".//Placemark")
            if not placemarks:
                result.parsing_status = ParsingStatus.FAILED
                result.errors.append("No <Placemark> elements found in KML file.")
                return result

            canonical_parcels: List[CanonicalParcel] = []
            valid_geom_count = 0

            for idx, pm in enumerate(placemarks):
                name_elem = pm.find("name")
                name_str = name_elem.text.strip() if name_elem is not None and name_elem.text else f"{source_label}-{idx + 1}"

                desc_elem = pm.find("description")
                desc_str = desc_elem.text.strip() if desc_elem is not None and desc_elem.text else ""

                # Extract ExtendedData attributes
                attrs: Dict[str, Any] = {"name": name_str, "description": desc_str}
                for data_elem in pm.findall(".//ExtendedData/Data"):
                    attr_name = data_elem.get("name")
                    val_elem = data_elem.find("value")
                    if attr_name and val_elem is not None and val_elem.text:
                        attrs[attr_name] = val_elem.text.strip()

                for simple_elem in pm.findall(".//ExtendedData/SimpleData"):
                    attr_name = simple_elem.get("name")
                    if attr_name and simple_elem.text:
                        attrs[attr_name] = simple_elem.text.strip()

                # Extract Polygon coordinates
                # Coordinates in KML are formatted as: lon,lat,alt lon,lat,alt ...
                polygons: List[Polygon] = []
                for poly_elem in pm.findall(".//Polygon"):
                    coord_elem = poly_elem.find(".//coordinates")
                    if coord_elem is not None and coord_elem.text:
                        raw_coords = coord_elem.text.strip().split()
                        ring = []
                        for coord_item in raw_coords:
                            parts = [p.strip() for p in coord_item.split(",") if p.strip()]
                            if len(parts) >= 2:
                                try:
                                    lon, lat = float(parts[0]), float(parts[1])
                                    ring.append((lon, lat))
                                except ValueError:
                                    continue
                        if len(ring) >= 3:
                            if ring[0] != ring[-1]:
                                ring.append(ring[0])
                            p_geom = Polygon(ring)
                            if p_geom.is_valid:
                                polygons.append(p_geom)

                geom_dict = None
                if polygons:
                    if len(polygons) == 1:
                        geom_dict = mapping(polygons[0])
                    else:
                        geom_dict = mapping(MultiPolygon(polygons))

                repaired = self.repair_geometry(geom_dict)
                if repaired:
                    valid_geom_count += 1

                geom_status = GeometryStatus.VALID_POLYGONS if repaired else GeometryStatus.INVALID_GEOMETRY

                pid = attrs.get("parcel_id") or attrs.get("survey_no") or name_str
                canonical_parcels.append(
                    CanonicalParcel(
                        parcel_id=str(pid),
                        geometry=repaired,
                        source=source_label,
                        survey_number=str(attrs.get("survey_number") or attrs.get("survey_no") or name_str),
                        land_use=str(attrs.get("land_use") or "Unknown"),
                        classification=str(attrs.get("classification") or "Unclassified"),
                        area=None,
                        attributes=attrs,
                        source_document=file_path.name,
                        confidence=0.95,
                        extraction_method="KML_PARSER",
                        crs="EPSG:4326",
                        geometry_status=geom_status,
                        field_confidences={
                            "parcel_id": FieldConfidence(value=str(pid), confidence=0.95, method="DIRECT"),
                            "survey_number": FieldConfidence(value=str(attrs.get("survey_number") or name_str), confidence=0.95, method="DIRECT"),
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
                "placemark_count": len(placemarks),
                "valid_geometry_count": valid_geom_count,
            }

        finally:
            shutil.rmtree(temp_dir, ignore_errors=True)

        return result
