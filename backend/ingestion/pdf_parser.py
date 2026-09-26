"""
backend/ingestion/pdf_parser.py
===============================
PDF land-record parser: extracts text and land attributes (Survey No, Area,
Land Use, Classification, Pattadar) using pypdf and OCR fallback.
Does NOT fabricate spatial coordinates from text-only deeds or diagrams.
"""

from __future__ import annotations

import re
import logging
from pathlib import Path
from typing import Optional, List, Dict, Any, Tuple

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

logger = logging.getLogger(__name__)

# Field extraction regex patterns tailored for Indian Cadastral / Revenue records (Telangana / AP / National)
SURVEY_PATTERNS = [
    r"(?:survey\s*(?:no|number)|sy\s*\.?\s*no|s\.no|khasra\s*(?:no|number)|plot\s*no)[\s.:/]*([0-9A-Za-z/_\-]+)",
    r"(?:rs\s*no|cts\s*no|t\.s\.\s*no)[\s.:/]*([0-9A-Za-z/_\-]+)",
]

AREA_PATTERNS = [
    r"(?:extent|area|total\s*area)[\s.:]*([0-9,.]+)\s*(acres?|guntas?|hectares?|sq\.?\s*yards?|sq\.?\s*meters?|sqm)",
    r"([0-9,.]+)\s*(acres?|guntas?|hectares?|sq\.?\s*yards?|sq\.?\s*meters?)\s*(?:of\s*land)?",
]

LAND_USE_PATTERNS = [
    r"(?:land\s*use|usage|category)[\s.:]*([A-Za-z\s]+?)(?:[,\n]|$)",
    r"\b(agricultural|residential|commercial|industrial|institutional|wet\s*land|dry\s*land)\b",
]

CLASSIFICATION_PATTERNS = [
    r"(?:classification|land\s*nature|tenure)[\s.:]*([A-Za-z\s]+?)(?:[,\n]|$)",
    r"\b(patta|inam|assigned|government|poramboke|waqf|bhoodan)\b",
]

OWNER_PATTERNS = [
    r"(?:pattadar|owner|title\s*holder|occupant|proprietor)[\s.:]*([A-Za-z\s.]+?)(?:[,\n]|$)",
    r"(?:khata\s*(?:no|number))[\s.:]*([0-9A-Za-z]+)",
]


def extract_regex_field(text: str, patterns: List[str]) -> Optional[Tuple[str, float]]:
    """Search for first matching pattern and return (value, confidence)."""
    for idx, pat in enumerate(patterns):
        m = re.search(pat, text, re.IGNORECASE)
        if m:
            val = m.group(1).strip()
            # If there's a unit group
            if len(m.groups()) >= 2 and m.group(2):
                val = f"{val} {m.group(2).strip()}"
            # Earlier patterns are higher confidence
            conf = 0.95 - (idx * 0.1)
            return val, max(conf, 0.6)
    return None


class PDFDocumentParser(BaseDocumentParser):
    """Parser for land-record PDFs (text and scanned)."""

    def can_parse(self, file_path: Path) -> bool:
        ext = file_path.suffix.lower()
        if ext == ".pdf":
            return True
        try:
            with open(file_path, "rb") as f:
                return f.read(5).startswith(b"%PDF-")
        except Exception:
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
            document_format="pdf",
            document_type="TEXT_DOCUMENT",
            crs_status=CRSStatus.NOT_APPLICABLE,
            geometry_status=GeometryStatus.METADATA_ONLY,
            has_spatial_geometry=False,
        )

        extracted_text = ""
        is_scanned = False
        page_count = 0

        try:
            from pypdf import PdfReader
            reader = PdfReader(str(file_path))
            page_count = len(reader.pages)
            for page in reader.pages:
                txt = page.extract_text()
                if txt:
                    extracted_text += "\n" + txt
        except Exception as exc:
            result.warnings.append(f"Text extraction failed with pypdf: {exc}")

        # If very little text was found, treat as scanned PDF and attempt OCR
        if len(extracted_text.strip()) < 50:
            is_scanned = True
            result.document_type = "SCANNED_IMAGE"
            # Delegate to OCR parser
            from .ocr_parser import OCRDocumentParser
            ocr_parser = OCRDocumentParser()
            ocr_text, ocr_conf, ocr_status = ocr_parser.ocr_pdf_pages(file_path)
            result.ocr_status = ocr_status
            if ocr_text:
                extracted_text = ocr_text
            else:
                result.parsing_status = ParsingStatus.PARTIAL
                result.errors.append("No text could be extracted from PDF (text extraction and OCR yielded no content).")
                result.extraction_confidence = ExtractionConfidence(
                    document_extraction_confidence=0.0,
                    geometry_confidence=0.0,
                )
                return result
        else:
            result.ocr_status = OCRStatus.NOT_APPLICABLE

        # Field Extraction
        field_confidences: Dict[str, FieldConfidence] = {}
        extraction_method = "OCR" if is_scanned else "PDF_TEXT_EXTRACT"

        # 1. Survey Number
        s_res = extract_regex_field(extracted_text, SURVEY_PATTERNS)
        survey_no = s_res[0] if s_res else f"DOC-{file_path.stem}"
        s_conf = s_res[1] if s_res else 0.5
        field_confidences["survey_number"] = FieldConfidence(
            value=survey_no,
            confidence=s_conf,
            method=extraction_method,
        )

        # 2. Area
        area_val = None
        a_res = extract_regex_field(extracted_text, AREA_PATTERNS)
        if a_res:
            field_confidences["area"] = FieldConfidence(
                value=a_res[0],
                confidence=a_res[1],
                method=extraction_method,
            )
            # Try parsing numeric area
            num_match = re.search(r"([0-9,.]+)", a_res[0])
            if num_match:
                try:
                    area_val = float(num_match.group(1).replace(",", ""))
                except ValueError:
                    area_val = None

        # 3. Land Use
        lu_res = extract_regex_field(extracted_text, LAND_USE_PATTERNS)
        land_use = lu_res[0] if lu_res else "Agricultural"
        lu_conf = lu_res[1] if lu_res else 0.5
        field_confidences["land_use"] = FieldConfidence(
            value=land_use,
            confidence=lu_conf,
            method=extraction_method,
        )

        # 4. Classification
        cl_res = extract_regex_field(extracted_text, CLASSIFICATION_PATTERNS)
        classification = cl_res[0] if cl_res else "Patta"
        cl_conf = cl_res[1] if cl_res else 0.5
        field_confidences["classification"] = FieldConfidence(
            value=classification,
            confidence=cl_conf,
            method=extraction_method,
        )

        # 5. Owner / Pattadar
        ow_res = extract_regex_field(extracted_text, OWNER_PATTERNS)
        attributes = {
            "source_type": "PDF_LAND_RECORD",
            "is_scanned": is_scanned,
            "page_count": page_count,
            "raw_text_snippet": extracted_text[:300].strip(),
        }
        if ow_res:
            field_confidences["pattadar"] = FieldConfidence(
                value=ow_res[0],
                confidence=ow_res[1],
                method=extraction_method,
            )
            attributes["pattadar"] = ow_res[0]

        # Assemble CanonicalParcel
        # CRITICAL: We NEVER invent coordinates if the PDF contains no spatial geometry.
        # Mark clearly: geometry=None, geometry_status=METADATA_ONLY.
        parcel = CanonicalParcel(
            parcel_id=survey_no,
            geometry=None,
            source=source_label,
            survey_number=survey_no,
            land_use=land_use,
            classification=classification,
            area=area_val,
            attributes=attributes,
            source_document=file_path.name,
            confidence=s_conf,
            extraction_method=extraction_method,
            crs=None,
            geometry_status=GeometryStatus.METADATA_ONLY,
            field_confidences=field_confidences,
        )

        result.parcels = [parcel]
        result.parsing_status = ParsingStatus.SUCCESS
        result.geometry_status = GeometryStatus.METADATA_ONLY
        result.has_spatial_geometry = False
        result.extraction_confidence = ExtractionConfidence(
            document_extraction_confidence=s_conf,
            geometry_confidence=0.0,  # Explicitly 0.0: non-spatial document
        )
        result.metadata = {
            "page_count": page_count,
            "is_scanned": is_scanned,
            "extracted_fields": list(field_confidences.keys()),
            "status_note": (
                "Document metadata successfully extracted. Spatial geometry is not present in "
                "this text record and must be reconciled against a spatial survey layer."
            ),
        }

        return result
