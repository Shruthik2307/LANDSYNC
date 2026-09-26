"""
backend/ingestion/image_parser.py
=================================
Image / scanned document parser for PNG, JPG, and TIFF deed records.
Extracts attributes via preprocessing & OCR, retaining explicit field confidences.
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Optional, Dict, Any

from .base import BaseDocumentParser
from .models import (
    DocumentParsingResult,
    CanonicalParcel,
    ParsingStatus,
    GeometryStatus,
    CRSStatus,
    OCRStatus,
    ExtractionConfidence,
    FieldConfidence,
)
from .ocr_parser import OCRDocumentParser
from .pdf_parser import (
    extract_regex_field,
    SURVEY_PATTERNS,
    AREA_PATTERNS,
    LAND_USE_PATTERNS,
    CLASSIFICATION_PATTERNS,
    OWNER_PATTERNS,
)

logger = logging.getLogger(__name__)


class ImageDocumentParser(BaseDocumentParser):
    """Parser for scanned deed/record images (PNG, JPG, TIFF)."""

    def can_parse(self, file_path: Path) -> bool:
        ext = file_path.suffix.lower()
        if ext in {".png", ".jpg", ".jpeg", ".tif", ".tiff"}:
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
            document_format=file_path.suffix.lstrip(".").lower(),
            document_type="SCANNED_IMAGE",
            crs_status=CRSStatus.NOT_APPLICABLE,
            geometry_status=GeometryStatus.METADATA_ONLY,
            has_spatial_geometry=False,
        )

        ocr_engine = OCRDocumentParser()
        text, avg_conf, ocr_status = ocr_engine.ocr_image(file_path)
        result.ocr_status = ocr_status

        field_confidences: Dict[str, FieldConfidence] = {}
        extraction_method = "OCR" if ocr_status == OCRStatus.COMPLETED else "IMAGE_METADATA"

        if text:
            # 1. Survey Number
            s_res = extract_regex_field(text, SURVEY_PATTERNS)
            survey_no = s_res[0] if s_res else f"SCAN-{file_path.stem}"
            s_conf = min(avg_conf, s_res[1] if s_res else 0.5)
            field_confidences["survey_number"] = FieldConfidence(
                value=survey_no, confidence=round(s_conf, 2), method="OCR"
            )

            # 2. Area
            area_val = None
            a_res = extract_regex_field(text, AREA_PATTERNS)
            if a_res:
                field_confidences["area"] = FieldConfidence(
                    value=a_res[0], confidence=round(min(avg_conf, a_res[1]), 2), method="OCR"
                )

            # 3. Land Use
            lu_res = extract_regex_field(text, LAND_USE_PATTERNS)
            land_use = lu_res[0] if lu_res else "Agricultural"
            field_confidences["land_use"] = FieldConfidence(
                value=land_use, confidence=round(min(avg_conf, lu_res[1] if lu_res else 0.5), 2), method="OCR"
            )

            # 4. Classification
            cl_res = extract_regex_field(text, CLASSIFICATION_PATTERNS)
            classification = cl_res[0] if cl_res else "Patta"
            field_confidences["classification"] = FieldConfidence(
                value=classification, confidence=round(min(avg_conf, cl_res[1] if cl_res else 0.5), 2), method="OCR"
            )

            # 5. Pattadar
            ow_res = extract_regex_field(text, OWNER_PATTERNS)
            if ow_res:
                field_confidences["pattadar"] = FieldConfidence(
                    value=ow_res[0], confidence=round(min(avg_conf, ow_res[1]), 2), method="OCR"
                )
        else:
            # No OCR engine or no text detected
            survey_no = f"IMG-{file_path.stem}"
            land_use = "Unknown"
            classification = "Unclassified"
            field_confidences["survey_number"] = FieldConfidence(
                value=survey_no, confidence=0.3, method="IMAGE_FILENAME_FALLBACK"
            )
            result.warnings.append(
                "Image text could not be extracted via OCR (Tesseract binary not installed or low resolution)."
            )

        parcel = CanonicalParcel(
            parcel_id=survey_no,
            geometry=None,
            source=source_label,
            survey_number=survey_no,
            land_use=land_use,
            classification=classification,
            area=None,
            attributes={
                "source_type": "SCANNED_IMAGE_DEED",
                "ocr_status": ocr_status.value,
                "text_snippet": text[:200].strip() if text else "",
            },
            source_document=file_path.name,
            confidence=avg_conf if text else 0.3,
            extraction_method=extraction_method,
            crs=None,
            geometry_status=GeometryStatus.METADATA_ONLY,
            field_confidences=field_confidences,
        )

        result.parcels = [parcel]
        result.parsing_status = ParsingStatus.SUCCESS if text else ParsingStatus.PARTIAL
        result.extraction_confidence = ExtractionConfidence(
            document_extraction_confidence=avg_conf if text else 0.3,
            geometry_confidence=0.0,
        )
        result.metadata = {
            "image_format": file_path.suffix.lstrip(".").upper(),
            "ocr_status": ocr_status.value,
            "status_note": "Scanned document metadata extracted. Non-spatial record (no polygon coordinates).",
        }

        return result
