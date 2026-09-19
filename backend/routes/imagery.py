"""
Imagery Upload Route
Handles aerial/drone imagery and GNSS data uploads
"""
import os
from fastapi import APIRouter, UploadFile, File, HTTPException
from pathlib import Path
import logging
import shutil
from typing import List
import rasterio
from config import settings
from services.imagery_service import ImageryProcessor, GNSSDataProcessor, LandRecordIntegration


router = APIRouter(prefix="/api", tags=["imagery"])
logger = logging.getLogger(__name__)

# Upload directory
UPLOAD_DIR = Path(__file__).parent.parent / "uploads" / "imagery"
UPLOAD_DIR.mkdir(parents=True, exist_ok=True)

imagery_processor = ImageryProcessor()
gnss_processor = GNSSDataProcessor()
land_records = LandRecordIntegration()


@router.post("/upload-imagery")
async def upload_imagery(
    files: List[UploadFile] = File(...),
    imagery_type: str = "aerial"
):
    """
    Upload aerial imagery, drone data, or GNSS survey files

    Args:
        files: Image files (GeoTIFF, PNG, JPG) or GNSS data (CSV, GeoJSON)
        imagery_type: aerial | drone | gnss

    Returns:
        Processing status and file paths
    """
    if not files:
        raise HTTPException(status_code=400, detail="No files provided")

    uploaded_files = []
    processed_files = []

    try:
        for file in files:
            # Check file size
            if file.size > settings.MAX_UPLOAD_SIZE:
                raise HTTPException(status_code=413, detail=f"File {file.filename} exceeds maximum upload size")

            # Save uploaded file - sanitize filename to prevent path traversal
            safe_filename = os.path.basename(file.filename)
            file_path = UPLOAD_DIR / safe_filename
            with open(file_path, "wb") as buffer:
                shutil.copyfileobj(file.file, buffer)
            uploaded_files.append(str(file_path))

            # Process based on type
            if imagery_type in ["aerial", "drone"]:
                processed_path = imagery_processor.process_aerial_image(
                    file_path,
                    UPLOAD_DIR
                )
                if processed_path:
                    processed_files.append(str(processed_path))
                    logger.info(f"Processed {imagery_type} imagery: {processed_path}")

            elif imagery_type == "gnss":
                # GNSS processing placeholder
                logger.info(f"GNSS data uploaded: {file_path}")
                processed_files.append(str(file_path))

        return {
            "status": "success",
            "uploaded_count": len(uploaded_files),
            "processed_count": len(processed_files),
            "files": processed_files
        }

    except (ValueError, RuntimeError) as e:
        logger.error(f"Imagery processing failed: {e}")
        raise HTTPException(status_code=422, detail="The imagery file could not be processed. Please verify format.")
    except Exception as e:
        logger.error(f"Unexpected imagery upload error: {e}")
        raise HTTPException(status_code=500, detail="An unexpected error occurred during imagery upload.")


@router.get("/imagery-status")
async def get_imagery_status():
    """
    Get status of uploaded imagery files

    Returns:
        Count and list of processed imagery
    """
    try:
        imagery_files = list(UPLOAD_DIR.glob("processed_*"))
        return {
            "total_files": len(imagery_files),
            "files": [f.name for f in imagery_files[:10]]
        }
    except Exception as e:
        logger.error(f"Failed to get imagery status: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/fetch-land-records/{parcel_id}")
async def fetch_land_records(parcel_id: str, source: str = "state_registry"):
    """
    Fetch land records from external registry

    Args:
        parcel_id: Parcel identifier
        source: Data source (state_registry, municipal_db)

    Returns:
        Land record data
    """
    try:
        record = land_records.fetch_land_records(parcel_id, source)
        if not record:
            raise HTTPException(status_code=404, detail=f"No records found for {parcel_id}")
        return record
    except Exception as e:
        logger.error(f"Failed to fetch land records: {e}")
        raise HTTPException(status_code=500, detail=str(e))
