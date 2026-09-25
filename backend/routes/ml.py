from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from database import get_db, Parcel
from pydantic import BaseModel
from typing import Optional
from services.ml_engine import get_conflict_prediction

router = APIRouter(prefix="/api/ml", tags=["ml-labeling"])

class LabelRequest(BaseModel):
    parcel_id: str
    label: int # 0: No Conflict, 1: Conflict
    confidence_override: Optional[float] = None
    notes: Optional[str] = None

class PredictionRequest(BaseModel):
    iou: float
    area_delta: float
    attr_match: float

@router.post("/predict")
async def predict_conflict(req: PredictionRequest):
    """Predict conflict level for a parcel based on GIS metrics."""
    prediction, reasoning = get_conflict_prediction(req.iou, req.area_delta, req.attr_match)
    if prediction == -1:
        raise HTTPException(status_code=503, detail="ML model currently unavailable")

    return {
        "conflict_level": prediction,
        "reasoning": reasoning
    }

@router.post("/label")
async def label_parcel(req: LabelRequest, db: Session = Depends(get_db)):
    parcel = db.query(Parcel).filter(Parcel.parcel_id == req.parcel_id).first()
    if not parcel:
        raise HTTPException(status_code=404, detail="Parcel not found")

    parcel.official_label = req.label
    db.commit()

    return {"status": "success", "message": f"Parcel {req.parcel_id} labeled as {req.label}"}
