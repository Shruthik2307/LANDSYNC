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
async def upload_dataset(
    file: UploadFile | None = File(None),
    files: list[UploadFile] | None = File(None),
) -> UploadResponse:
    """Upload one or more GeoJSON datasets.

    - Accepts a single 'file' or multiple 'files' (e.g. Cadastral + Municipal).
    - Validates file extension (.geojson / .json) and size (max 500MB).
    - Validates that each file is valid GeoJSON (FeatureCollection with features).
    - Saves to uploads/ directory prefixed with a shared dataset_id.
    - Returns a dataset_id for use with POST /api/process.
    """
    # ── Collect incoming files ─────────────────────────────────────────────
    incoming: list[UploadFile] = []
    if files:
        incoming.extend(files)
    if file and file not in incoming:
        # Avoid duplicate if same file sent as both 'file' and 'files'
        if not any(f.filename == file.filename for f in incoming):
            incoming.append(file)

    if not incoming:
        raise HTTPException(
            status_code=400,
            detail="No files provided. Please upload a GeoJSON file.",
        )

    dataset_id = f"ds_{uuid.uuid4().hex[:12]}"
    saved_paths: list[Path] = []

    try:
        for f in incoming:
            filename = f.filename or "upload.geojson"
            ext = Path(filename).suffix.lower()
            if ext not in _ALLOWED_EXTENSIONS:
                raise HTTPException(
                    status_code=400,
                    detail=(
                        f"Unsupported file type: {ext!r}. "
                        f"Allowed extensions: {', '.join(sorted(_ALLOWED_EXTENSIONS))}"
                    ),
                )

            safe_filename = os.path.basename(filename)
            save_path = _UPLOAD_DIR / f"{dataset_id}_{safe_filename}"
            total_bytes = 0

            try:
                with open(save_path, "wb") as buffer:
                    while chunk := await f.read(1024 * 1024):  # 1MB chunks
                        total_bytes += len(chunk)
                        if total_bytes > _MAX_UPLOAD_BYTES:
                            raise HTTPException(
                                status_code=413,
                                detail=f"File {filename!r} exceeds maximum allowed size (500 MB).",
                            )
                        buffer.write(chunk)
            except OSError as exc:
                logger.error("[upload] Failed to save uploaded file %s: %s", filename, exc)
                raise HTTPException(status_code=500, detail="Server could not save the uploaded file.")

            saved_paths.append(save_path)
            file_size = save_path.stat().st_size
            feature_count = 0

            # ── Validate GeoJSON Content ──────────────────────────────────
            if file_size > 20 * 1024 * 1024:
                # Large file header check
                with open(save_path, "r", encoding="utf-8", errors="ignore") as fp:
                    header = fp.read(4096)
                    if '"FeatureCollection"' not in header and "'FeatureCollection'" not in header:
                        raise HTTPException(
                            status_code=400,
                            detail=f"Invalid GeoJSON in {filename!r}. The root object must have 'type': 'FeatureCollection'.",
                        )
                feature_count = -1
            else:
                with open(save_path, "rb") as fp:
                    content = fp.read()

                try:
                    geojson = json.loads(content)
                except json.JSONDecodeError as err:
                    raise HTTPException(
                        status_code=400,
                        detail=f"Uploaded file {filename!r} is not valid JSON ({err.msg} at line {err.lineno}, col {err.colno}).",
                    )

                if not isinstance(geojson, dict) or geojson.get("type") != "FeatureCollection":
                    raise HTTPException(
                        status_code=400,
                        detail=f"Invalid GeoJSON in {filename!r}. The root object must have 'type': 'FeatureCollection'.",
                    )

                features = geojson.get("features", [])
                if not features:
                    raise HTTPException(
                        status_code=400,
                        detail=f"GeoJSON in {filename!r} contains no features. Please upload a FeatureCollection containing at least one parcel feature.",
                    )
                feature_count = len(features)

            logger.info(
                "[upload] Saved file %r for dataset %r (%s features, %.1f MB)",
                save_path.name,
                dataset_id,
                str(feature_count) if feature_count >= 0 else "large",
                file_size / (1024 * 1024),
            )

    except Exception:
        # Cleanup all saved files on failure
        for p in saved_paths:
            if p.exists():
                try:
                    os.remove(p)
                except Exception:
                    pass
        raise

    return UploadResponse(dataset_id=dataset_id)


