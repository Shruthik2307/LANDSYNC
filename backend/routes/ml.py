from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from database import get_db, Parcel
from pydantic import BaseModel
from typing import Optional

router = APIRouter(prefix="/api/ml", tags=["ml-labeling"])

class LabelRequest(BaseModel):
    parcel_id: str
    label: int # 0: No Conflict, 1: Conflict
    confidence_override: Optional[float] = None
    notes: Optional[str] = None

@router.post("/label")
async def label_parcel(req: LabelRequest, db: Session = Depends(get_db)):
    parcel = db.query(Parcel).filter(Parcel.parcel_id == req.parcel_id).first()
    if not parcel:
        raise HTTPException(status_code=404, detail="Parcel not found")
    
    parcel.official_label = req.label
    # Note: labeled_by would be set here if we have current_user from auth
    db.commit()
    
    return {"status": "success", "message": f"Parcel {req.parcel_id} labeled as {req.label}"}
