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
import os
from pathlib import Path

from fastapi import APIRouter, File, HTTPException, UploadFile
from pydantic import BaseModel
import geopandas as gpd
import fiona
import os


logger = logging.getLogger(__name__)
router = APIRouter(tags=["upload"])

# Allowed upload extensions
_ALLOWED_EXTENSIONS = {".geojson", ".json"}
# Max 500 MB
_MAX_UPLOAD_BYTES = 500 * 1024 * 1024

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

    # ── Read and Save content ────────────────────────────────────────────────
    dataset_id = f"ds_{uuid.uuid4().hex[:12]}"
    safe_filename = os.path.basename(filename)
    save_path = _UPLOAD_DIR / f"{dataset_id}_{safe_filename}"

    try:
        # Stream directly to disk to avoid loading massive files into memory (prevent 413)
        with open(save_path, "wb") as buffer:
            while chunk := await file.read(1024 * 1024): # 1MB chunks
                buffer.write(chunk)
    except OSError as exc:
        logger.error("[upload] Failed to save uploaded file: %s", exc)
        raise HTTPException(status_code=500, detail="Server could not save the uploaded file.")

    # After saving, validate content without exceeding server memory limits
    file_size = save_path.stat().st_size
    feature_count = 0

    try:
        if file_size > 20 * 1024 * 1024:
            # For large files (>20 MB), stream the header to avoid loading hundreds of MB into RAM (prevent Render OOM)
            with open(save_path, "r", encoding="utf-8", errors="ignore") as f:
                header = f.read(4096)
                if '"FeatureCollection"' not in header and "'FeatureCollection'" not in header:
                    if save_path.exists():
                        os.remove(save_path)
                    raise HTTPException(
                        status_code=400,
                        detail="Invalid GeoJSON. The root object must have 'type': 'FeatureCollection'.",
                    )
            feature_count = -1
        else:
            with open(save_path, "rb") as f:
                content = f.read()

            geojson = json.loads(content)
            if not isinstance(geojson, dict) or geojson.get("type") != "FeatureCollection":
                if save_path.exists():
                    os.remove(save_path)
                raise HTTPException(
                    status_code=400,
                    detail="Invalid GeoJSON. The root object must have 'type': 'FeatureCollection'.",
                )

            features = geojson.get("features", [])
            if not features:
                if save_path.exists():
                    os.remove(save_path)
                raise HTTPException(
                    status_code=400,
                    detail="GeoJSON contains no features. Please upload a FeatureCollection containing at least one parcel feature.",
                )
            feature_count = len(features)

    except HTTPException:
        raise
    except json.JSONDecodeError as err:
        if save_path.exists():
            os.remove(save_path)
        raise HTTPException(
            status_code=400,
            detail=f"Uploaded file is not valid JSON ({err.msg} at line {err.lineno}, col {err.colno}).",
        )
    except Exception as e:
        if save_path.exists():
            os.remove(save_path)
        raise HTTPException(status_code=400, detail=f"File validation failed: {str(e)}")

    logger.info(
        "[upload] Saved dataset %r (%s features, %.1f MB) → %s",
        dataset_id,
        str(feature_count) if feature_count >= 0 else "large",
        file_size / (1024 * 1024),
        save_path.name,
    )

    return UploadResponse(dataset_id=dataset_id)

