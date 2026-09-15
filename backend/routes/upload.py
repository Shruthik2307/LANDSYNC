"""
backend/routes/upload.py
========================
POST /api/upload — accept a GeoJSON file upload.

Phase 1 behaviour
-----------------
• Validates the file extension (.geojson / .json).
• Validates that the file parses as valid JSON with a "features" key.
• Saves the file to backend/uploads/.
• Returns { dataset_id: str } — compatible with the OpenAPI contract.
• Does NOT immediately trigger reconciliation; that is POST /api/process.

The uploaded file is stored as backend/uploads/<dataset_id>_<original_filename>.
The dataset_id is returned so the frontend can pass it to /api/process.
"""

from __future__ import annotations

import json
import logging
import uuid
from pathlib import Path

from fastapi import APIRouter, File, HTTPException, UploadFile
from pydantic import BaseModel

logger = logging.getLogger(__name__)
router = APIRouter(tags=["upload"])

# Allowed upload extensions
_ALLOWED_EXTENSIONS = {".geojson", ".json"}
# Max 50 MB
_MAX_UPLOAD_BYTES = 50 * 1024 * 1024

# Upload directory (relative to backend/)
_UPLOAD_DIR = Path(__file__).resolve().parent.parent / "uploads"
_UPLOAD_DIR.mkdir(exist_ok=True)


class UploadResponse(BaseModel):
    """Response from a successful file upload."""
    dataset_id: str


@router.post("/api/upload", response_model=UploadResponse)
async def upload_dataset(file: UploadFile = File(...)) -> UploadResponse:
    """Upload a GeoJSON dataset.

    - Validates file extension and size.
    - Validates that the file is valid GeoJSON (FeatureCollection with features).
    - Saves to uploads/ directory.
    - Returns a dataset_id for use with POST /api/process.
    """
    # ── Extension check ───────────────────────────────────────────────────
    filename = file.filename or "upload.geojson"
    ext = Path(filename).suffix.lower()
    if ext not in _ALLOWED_EXTENSIONS:
        raise HTTPException(
            status_code=400,
            detail=(
                f"Unsupported file type: {ext!r}. "
                f"Allowed extensions: {', '.join(sorted(_ALLOWED_EXTENSIONS))}"
            ),
        )

    # ── Read content ──────────────────────────────────────────────────────
    content = await file.read()

    if len(content) == 0:
        raise HTTPException(status_code=400, detail="Uploaded file is empty.")

    if len(content) > _MAX_UPLOAD_BYTES:
        max_mb = _MAX_UPLOAD_BYTES // (1024 * 1024)
        raise HTTPException(
            status_code=413,
            detail=f"File too large. Maximum allowed size is {max_mb} MB.",
        )

    # ── JSON validation ───────────────────────────────────────────────────
    try:
        geojson = json.loads(content)
    except json.JSONDecodeError as exc:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid JSON: {exc}",
        )

    if not isinstance(geojson, dict):
        raise HTTPException(
            status_code=400,
            detail="GeoJSON root must be a JSON object (FeatureCollection).",
        )

    geojson_type = geojson.get("type", "")
    if geojson_type != "FeatureCollection":
        raise HTTPException(
            status_code=400,
            detail=(
                f"Expected GeoJSON type 'FeatureCollection', "
                f"got {geojson_type!r}."
            ),
        )

    features = geojson.get("features")
    if not isinstance(features, list) or len(features) == 0:
        raise HTTPException(
            status_code=400,
            detail="GeoJSON FeatureCollection has no features.",
        )

    # ── Save file ─────────────────────────────────────────────────────────
    dataset_id = f"ds_{uuid.uuid4().hex[:12]}"
    save_path = _UPLOAD_DIR / f"{dataset_id}_{filename}"

    try:
        save_path.write_bytes(content)
    except OSError as exc:
        logger.error("[upload] Failed to save uploaded file: %s", exc)
        raise HTTPException(
            status_code=500,
            detail="Server could not save the uploaded file.",
        )

    logger.info(
        "[upload] Saved dataset %r (%d features, %.1f KB) → %s",
        dataset_id,
        len(features),
        len(content) / 1024,
        save_path.name,
    )

    return UploadResponse(dataset_id=dataset_id)
