"""
backend/ingestion/validation.py
===============================
Security validation, magic-byte checks, archive-bomb defenses, and
path traversal guards for uploaded files.
"""

from __future__ import annotations

import os
import re
import zipfile
import logging
from pathlib import Path
from typing import Tuple, Optional, Set

logger = logging.getLogger(__name__)

# Size limits (bytes)
MAX_FILE_SIZE = 500 * 1024 * 1024        # 500 MB overall limit
MAX_UNCOMPRESSED_ZIP_SIZE = 250 * 1024 * 1024  # 250 MB max uncompressed archive
MAX_ZIP_COMPRESSION_RATIO = 100           # Bomb protection: ratio > 100:1 rejected
MAX_IMAGE_FILE_SIZE = 50 * 1024 * 1024    # 50 MB for images
MAX_PDF_FILE_SIZE = 50 * 1024 * 1024      # 50 MB for PDFs

# Known Magic Signatures
_MAGIC_SIGNATURES = {
    "pdf": [b"%PDF-"],
    "zip": [b"PK\x03\x04", b"PK\x05\x06", b"PK\x07\x08"],
    "png": [b"\x89PNG\r\n\x1a\n"],
    "jpeg": [b"\xff\xd8\xff"],
    "tiff_le": [b"II*\x00"],
    "tiff_be": [b"MM\x00*"],
    "sqlite": [b"SQLite format 3\x00"],  # GeoPackage (.gpkg) is an SQLite database
    "dwg": [b"AC10"],                    # Autodesk DWG format header
}


def sanitize_filename(filename: str) -> str:
    """Sanitize user-provided filename to prevent path traversal or shell exploits."""
    base = os.path.basename(filename).strip()
    safe = re.sub(r'[^a-zA-Z0-9_.\-]', '_', base)
    if not safe or safe in {".", ".."}:
        return "uploaded_document"
    return safe


def validate_file_size(file_path: Path, max_bytes: int = MAX_FILE_SIZE) -> None:
    """Validate that the file does not exceed size limits."""
    size = file_path.stat().st_size
    if size > max_bytes:
        raise ValueError(
            f"File exceeds maximum allowed size: {size / (1024 * 1024):.1f} MB > {max_bytes / (1024 * 1024):.1f} MB"
        )
    if size == 0:
        raise ValueError("Uploaded file is empty (0 bytes).")


def detect_file_type(file_path: Path) -> Tuple[str, str]:
    """Detect file type using extension and magic bytes.

    Returns (format_category, extension).
    format_category: 'geojson', 'shapefile_zip', 'kml', 'kmz', 'geopackage',
                     'dxf', 'dwg', 'pdf', 'image', 'geotiff', 'unknown'
    """
    ext = file_path.suffix.lower()
    
    with open(file_path, "rb") as f:
        header = f.read(32)

    # 1. GeoJSON / JSON
    if ext in {".geojson", ".json"}:
        return "geojson", ext

    # 2. PDF
    if ext == ".pdf" or header.startswith(b"%PDF-"):
        return "pdf", ".pdf"

    # 3. Shapefile or KMZ (ZIP archives)
    if header.startswith((b"PK\x03\x04", b"PK\x05\x06")):
        if ext == ".kmz":
            return "kmz", ext
        return "shapefile_zip", ".zip"

    # 4. KML
    if ext == ".kml":
        return "kml", ext

    # 5. GeoPackage (.gpkg)
    if ext == ".gpkg" or header.startswith(b"SQLite format 3\x00"):
        return "geopackage", ".gpkg"

    # 6. DXF
    if ext == ".dxf":
        return "dxf", ".dxf"

    # 7. DWG
    if ext == ".dwg" or header.startswith(b"AC10"):
        return "dwg", ".dwg"

    # 8. GeoTIFF / TIFF
    if ext in {".tif", ".tiff"} or header.startswith((b"II*\x00", b"MM\x00*")):
        return "geotiff", ext

    # 9. Images (PNG, JPG, JPEG)
    if ext in {".png", ".jpg", ".jpeg"} or header.startswith((b"\x89PNG\r\n\x1a\n", b"\xff\xd8\xff")):
        return "image", ext

    return "unknown", ext


def validate_and_extract_safe_zip(
    zip_path: Path,
    dest_dir: Path,
    required_extensions: Optional[Set[str]] = None,
) -> List[Path]:
    """Safely extracts a ZIP archive preventing ZipSlip and archive bombs.

    Validates:
      - Total extracted size does not exceed MAX_UNCOMPRESSED_ZIP_SIZE.
      - Compression ratio does not exceed MAX_ZIP_COMPRESSION_RATIO.
      - No directory traversal (.. or absolute paths).
      - Checks for required extensions (e.g. .shp, .shx, .dbf for shapefiles).
    """
    if not zipfile.is_zipfile(zip_path):
        raise ValueError("File is not a valid ZIP archive.")

    total_uncompressed = 0
    extracted_files: List[Path] = []
    found_extensions: Set[str] = set()

    with zipfile.ZipFile(zip_path, "r") as zf:
        # Check archive bomb metrics
        compressed_size = zip_path.stat().st_size
        for info in zf.infolist():
            total_uncompressed += info.file_size
            found_extensions.add(Path(info.filename).suffix.lower())

        if total_uncompressed > MAX_UNCOMPRESSED_ZIP_SIZE:
            raise ValueError(
                f"Archive uncompressed size ({total_uncompressed / (1024*1024):.1f} MB) exceeds maximum allowed limit."
            )

        if compressed_size > 0 and (total_uncompressed / compressed_size) > MAX_ZIP_COMPRESSION_RATIO:
            raise ValueError("Potential archive bomb detected: compression ratio exceeds safety threshold.")

        if required_extensions and not required_extensions.issubset(found_extensions):
            missing = required_extensions - found_extensions
            raise ValueError(f"Archive missing required files: {', '.join(sorted(missing))}")

        # Safe extraction
        dest_resolved = dest_dir.resolve()
        for member in zf.infolist():
            # Prevent ZipSlip
            target_path = (dest_dir / member.filename).resolve()
            if not str(target_path).startswith(str(dest_resolved)):
                raise ValueError(f"Path traversal detected in ZIP entry: {member.filename!r}")

            if member.is_dir():
                target_path.mkdir(parents=True, exist_ok=True)
            else:
                target_path.parent.mkdir(parents=True, exist_ok=True)
                with zf.open(member) as src, open(target_path, "wb") as dst:
                    while chunk := src.read(1024 * 1024):
                        dst.write(chunk)
                extracted_files.append(target_path)

    return extracted_files
