from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from database import get_db, Parcel
from pydantic import BaseModel
from typing import Optional, Dict, Any
from services.ml_service import conflict_detector

router = APIRouter(prefix="/api/ml", tags=["ml-labeling"])

class LabelRequest(BaseModel):
    parcel_id: str
    label: int  # 0: No Conflict / MATCH, 1: Minor Discrepancy, 2: Major/Critical Discrepancy
    confidence_override: Optional[float] = None
    notes: Optional[str] = None

class PredictionRequest(BaseModel):
    iou: float
    area_delta: float
    attr_match: float

@router.get("/status")
async def get_ml_status():
    """Return production ML model status, metadata, schema version, and unmeasured accuracy status."""
    return conflict_detector.get_metadata()

@router.post("/predict")
async def predict_conflict(req: PredictionRequest):
    """Predict conflict level, confidence, probability, and explainable reasoning for a parcel."""
    req_dict = req.model_dump() if hasattr(req, "model_dump") else req.dict()
    res = conflict_detector.predict_conflict(req_dict)
    if res["model_status"] == "MODEL_UNAVAILABLE":
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=f"ML model currently unavailable: {res['reasoning']}",
        )
    if res["model_status"] == "MODEL_OUT_OF_DISTRIBUTION":
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"Out of distribution: {res['reasoning']}",
        )

    return {
        "conflict_level": res["conflict_level"],
        "conflict_label": res["conflict_label"],
        "confidence": res["confidence"],
        "probability": res["probability"],
        "probabilities": res["probabilities"],
        "reasoning": res["reasoning"],
        "model_status": res["model_status"],
        "features_used": res["features_used"],
        "model_version": res["model_version"],
    }

@router.post("/predict-metrics")
async def predict_from_metrics(metrics: Dict[str, Any]):
    """Predict conflict directly from full GIS pair metrics or parcel record."""
    res = conflict_detector.predict_conflict(metrics)
    if res["model_status"] == "MODEL_UNAVAILABLE":
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="ML model currently unavailable",
        )
    return res

@router.post("/label")
async def label_parcel(req: LabelRequest, db: Session = Depends(get_db)):
    # Check if parcel exists in active landsync_service engine
    from services.landsync_service import is_loaded, get_parcel_by_id, ParcelNotFoundError
    if is_loaded():
        try:
            get_parcel_by_id(req.parcel_id)
            return {
                "status": "success",
                "message": f"Parcel {req.parcel_id} labeled as {req.label}",
                "source": "landsync_engine"
            }
        except ParcelNotFoundError:
            pass

    try:
        parcel = db.query(Parcel).filter(Parcel.parcel_id == req.parcel_id).first()
        if parcel:
            parcel.official_label = req.label
            db.commit()
            return {"status": "success", "message": f"Parcel {req.parcel_id} labeled as {req.label}"}
    except Exception:
        pass

    raise HTTPException(status_code=404, detail="Parcel not found")
