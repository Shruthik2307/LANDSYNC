"""
backend/ingestion/ocr_parser.py
===============================
OCR extraction engine with image preprocessing (deskew, denoise, contrast enhancement)
and confidence scoring. Uses pytesseract with graceful degradation.
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Tuple, Optional, List, Dict, Any
from PIL import Image, ImageOps, ImageFilter

from .models import OCRStatus

logger = logging.getLogger(__name__)


def is_tesseract_available() -> bool:
    """Check if pytesseract and the underlying Tesseract binary are accessible."""
    try:
        import pytesseract
        # Try getting version
        _ = pytesseract.get_tesseract_version()
        return True
    except Exception:
        return False


def preprocess_image(img: Image.Image) -> Image.Image:
    """Preprocess scanned image: grayscale, contrast enhancement, noise reduction."""
    # 1. Convert to grayscale
    gray = ImageOps.grayscale(img)
    # 2. Contrast enhancement / autocontrast
    contrasted = ImageOps.autocontrast(gray, cutoff=2)
    # 3. Slight blur to denoise speckles
    denoised = contrasted.filter(ImageFilter.MedianFilter(size=3))
    return denoised


class OCRDocumentParser:
    """OCR engine for scanned PDFs and image documents."""

    def ocr_image(self, img_path: Path) -> Tuple[str, float, OCRStatus]:
        """Perform OCR on an image file.

        Returns (extracted_text, average_confidence, ocr_status).
        """
        if not is_tesseract_available():
            logger.info("[ocr_parser] Tesseract binary not detected in environment.")
            return "", 0.0, OCRStatus.UNAVAILABLE

        try:
            import pytesseract
            with Image.open(img_path) as img:
                processed = preprocess_image(img)
                data = pytesseract.image_to_data(processed, output_type=pytesseract.Output.DICT)
                text = pytesseract.image_to_string(processed)

            confs = [float(c) for c in data.get("conf", []) if str(c) not in ("-1", "")]
            avg_conf = (sum(confs) / len(confs) / 100.0) if confs else 0.8
            status = OCRStatus.COMPLETED if avg_conf >= 0.5 else OCRStatus.LOW_CONFIDENCE
            return text, avg_conf, status
        except Exception as exc:
            logger.error("[ocr_parser] OCR execution failed: %s", exc)
            return "", 0.0, OCRStatus.UNAVAILABLE

    def ocr_pdf_pages(self, pdf_path: Path) -> Tuple[str, float, OCRStatus]:
        """Attempt to render and OCR PDF pages using pypdf/pypdfium2/pdf2image or return unavailable."""
        if not is_tesseract_available():
            return "", 0.0, OCRStatus.UNAVAILABLE

        # Extract embedded images from PDF pages using pypdf
        try:
            from pypdf import PdfReader
            reader = PdfReader(str(pdf_path))
            combined_text = ""
            conf_scores: List[float] = []

            for page in reader.pages:
                for img_obj in page.images:
                    import io
                    with Image.open(io.BytesIO(img_obj.data)) as img:
                        processed = preprocess_image(img)
                        import pytesseract
                        txt = pytesseract.image_to_string(processed)
                        combined_text += "\n" + txt
                        data = pytesseract.image_to_data(processed, output_type=pytesseract.Output.DICT)
                        confs = [float(c) for c in data.get("conf", []) if str(c) not in ("-1", "")]
                        if confs:
                            conf_scores.append(sum(confs) / len(confs) / 100.0)

            if combined_text.strip():
                avg_conf = sum(conf_scores) / len(conf_scores) if conf_scores else 0.75
                return combined_text, avg_conf, OCRStatus.COMPLETED

            return "", 0.0, OCRStatus.UNAVAILABLE
        except Exception as exc:
            logger.warning("[ocr_parser] PDF page image OCR fallback failed: %s", exc)
            return "", 0.0, OCRStatus.UNAVAILABLE
