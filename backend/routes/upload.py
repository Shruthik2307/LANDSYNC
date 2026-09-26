"""
backend/routes/upload.py
========================
POST /api/upload — Multi-format land document ingestion endpoint.

Supports:
- GeoJSON / JSON
- PDF (text and scanned documents via OCR)
- Images (PNG, JPG, TIFF)
- CAD (DXF vector extraction, DWG guidance)
- Shapefile (.zip with .shp, .shx, .dbf, .prj)
- KML / KMZ
- GeoPackage (.gpkg)
- GeoTIFF raster survey

Vector spatial geometries are converted to canonical FeatureCollections
so that the existing reconciliation engine (POST /api/process) operates
without modifying the ML model or reconciliation pipeline.
"""

from __future__ import annotations

import json
import logging
import uuid
import os
from pathlib import Path
from typing import List, Optional, Dict, Any

from fastapi import APIRouter, File, Form, HTTPException, UploadFile
from pydantic import BaseModel, Field

from ingestion.models import (
    DocumentParsingResult,
    ParsingStatus,
    GeometryStatus,
    CRSStatus,
)
from ingestion.router import (
    parse_document,
    sync_to_geojson_cache,
)
from ingestion.validation import (
    sanitize_filename,
    validate_file_size,
    MAX_FILE_SIZE,
)

logger = logging.getLogger(__name__)
router = APIRouter(tags=["upload"])

# Allowed upload extensions
_ALLOWED_EXTENSIONS = {
    ".geojson", ".json",
    ".pdf",
    ".png", ".jpg", ".jpeg", ".tif", ".tiff",
    ".dxf", ".dwg",
    ".zip", ".shp",
    ".kml", ".kmz",
    ".gpkg",
}

_UPLOAD_DIR = Path(__file__).resolve().parent.parent / "uploads"
_UPLOAD_DIR.mkdir(exist_ok=True)


class FileParsingSummary(BaseModel):
    filename: str
    format: str
    document_type: str
    parsing_status: str
    ocr_status: str
    geometry_status: str
    crs_status: str
    source_crs: Optional[str] = None
    feature_count: int = 0
    has_spatial_geometry: bool = False
    extraction_confidence: float = 1.0
    errors: List[str] = Field(default_factory=list)
    warnings: List[str] = Field(default_factory=list)


class UploadResponse(BaseModel):
    """Response from a file upload (backward-compatible with OpenAPI contract)."""
    dataset_id: str
    files_received: int = 1
    parsing_summaries: List[FileParsingSummary] = Field(default_factory=list)
    ready_for_reconciliation: bool = True
    notice: Optional[str] = None


@router.post("/api/upload", response_model=UploadResponse)
async def upload_dataset(
    file: UploadFile | None = File(None),
    files: list[UploadFile] | None = File(None),
    crs_hint: Optional[str] = Form(None),
) -> UploadResponse:
    """Upload one or more land records in any supported format."""
    incoming: list[UploadFile] = []
    if files:
        incoming.extend(files)
    if file and file not in incoming:
        if not any(f.filename == file.filename for f in incoming):
            incoming.append(file)

    if not incoming:
        raise HTTPException(
            status_code=400,
            detail="No files provided. Please upload land documents or geospatial files.",
        )

    dataset_id = f"ds_{uuid.uuid4().hex[:12]}"
    saved_paths: list[Path] = []
    parsing_results: list[DocumentParsingResult] = []

    try:
        for f in incoming:
            raw_filename = f.filename or "upload.geojson"
            ext = Path(raw_filename).suffix.lower()
            if ext not in _ALLOWED_EXTENSIONS:
                raise HTTPException(
                    status_code=400,
                    detail=(
                        f"Unsupported file type: {ext!r}. "
                        f"Supported formats: GeoJSON, JSON, PDF, PNG, JPG, TIFF, DXF, SHP ZIP, KML, KMZ, GPKG."
                    ),
                )

            safe_name = sanitize_filename(raw_filename)
            save_path = _UPLOAD_DIR / f"{dataset_id}_{safe_name}"
            total_bytes = 0

            with open(save_path, "wb") as buffer:
                while chunk := await f.read(1024 * 1024):  # 1MB chunks
                    total_bytes += len(chunk)
                    if total_bytes > MAX_FILE_SIZE:
                        raise HTTPException(
                            status_code=413,
                            detail=f"File {raw_filename!r} exceeds maximum allowed size (500 MB).",
                        )
                    buffer.write(chunk)

            saved_paths.append(save_path)

            # Smart label determination
            name_lower = safe_name.lower()
            cadastral_clues = ("cadastr", "revenue", "ror", "khasra", "deed", "land_record", "rev")
            municipal_clues = ("municip", "survey", "ulb", "drone", "town", "ghmc", "mun")

            if any(c in name_lower for c in cadastral_clues):
                label = "cadastral"
            elif any(m in name_lower for m in municipal_clues):
                label = "municipal"
            else:
                label = "cadastral" if len(saved_paths) == 1 else "municipal"

            # Parse with format-agnostic ingestion engine
            parse_res = parse_document(
                file_path=save_path,
                crs_hint=crs_hint,
                source_label=label,
            )
            parsing_results.append(parse_res)

            # Check if this was a failure or unsupported format
            if parse_res.parsing_status in (ParsingStatus.FAILED, ParsingStatus.UNSUPPORTED_FORMAT):
                err_msg = "; ".join(parse_res.errors) if parse_res.errors else "Unknown parsing error."
                raise HTTPException(
                    status_code=400,
                    detail=f"Failed to parse {raw_filename!r}: {err_msg}",
                )

        # Convert spatial vector parcels to canonical GeoJSON in _UPLOAD_DIR
        # so existing reconciliation engine can load them via dataset_id
        generated_geojsons = sync_to_geojson_cache(
            dataset_id=dataset_id,
            parsing_results=parsing_results,
            target_dir=_UPLOAD_DIR,
        )

        # Build response summaries
        summaries: list[FileParsingSummary] = []
        has_any_spatial = False

        for res in parsing_results:
            feat_count = len(res.parcels)
            if res.has_spatial_geometry:
                has_any_spatial = True

            summaries.append(
                FileParsingSummary(
                    filename=res.document_name,
                    format=res.document_format,
                    document_type=res.document_type,
                    parsing_status=res.parsing_status.value,
                    ocr_status=res.ocr_status.value,
                    geometry_status=res.geometry_status.value,
                    crs_status=res.crs_status.value,
                    source_crs=res.source_crs,
                    feature_count=feat_count,
                    has_spatial_geometry=res.has_spatial_geometry,
                    extraction_confidence=res.extraction_confidence.document_extraction_confidence,
                    errors=res.errors,
                    warnings=res.warnings,
                )
            )

        # Save manifest to disk
        manifest_path = _UPLOAD_DIR / f"{dataset_id}_manifest.json"
        manifest_payload = {
            "dataset_id": dataset_id,
            "summaries": [s.model_dump() for s in summaries],
            "has_spatial_geometry": has_any_spatial,
            "generated_geojsons": [p.name for p in generated_geojsons],
        }
        with open(manifest_path, "w", encoding="utf-8") as f:
            json.dump(manifest_payload, f, indent=2)

        notice = None
        if not has_any_spatial:
            notice = (
                "Document metadata successfully extracted (deed/record fields parsed). "
                "Spatial boundaries were not found; for spatial reconciliation, also upload a geospatial survey layer."
            )

        return UploadResponse(
            dataset_id=dataset_id,
            files_received=len(incoming),
            parsing_summaries=summaries,
            ready_for_reconciliation=has_any_spatial,
            notice=notice,
        )

    except HTTPException:
        # Cleanup files on failure
        for p in saved_paths:
            if p.exists():
                try:
                    os.remove(p)
                except Exception:
                    pass
        raise
    except Exception as exc:
        logger.error("[upload] Unexpected error during upload: %s", exc, exc_info=True)
        for p in saved_paths:
            if p.exists():
                try:
                    os.remove(p)
                except Exception:
                    pass
        raise HTTPException(status_code=500, detail=f"Server error during document processing: {exc}")


@router.get("/api/upload/manifest/{dataset_id}")
def get_upload_manifest(dataset_id: str) -> Dict[str, Any]:
    """Retrieve the parsing manifest and field confidence breakdown for an uploaded dataset."""
    manifest_path = _UPLOAD_DIR / f"{dataset_id}_manifest.json"
    if not manifest_path.exists():
        raise HTTPException(status_code=404, detail="Upload manifest not found for this dataset ID.")

    with open(manifest_path, "r", encoding="utf-8") as f:
        return json.load(f)
