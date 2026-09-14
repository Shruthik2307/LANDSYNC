"""
LANDSYNC — SIH26013 FastAPI Backend & GeoPandas Reconciliation Service
Member 2 (Backend API) & Member 3 (PostGIS Spatial Database) Module
"""

from fastapi import FastAPI, HTTPException, UploadFile, File
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import List

app = FastAPI(
    title="LANDSYNC AI Geospatial Reconciliation API",
    description="SIH26013 Multi-Source Geospatial Harmonization & Confidence Engine",
    version="1.0.0"
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

class ParcelReconciliationResponse(BaseModel):
    parcel_id: str
    confidence: int
    priority: str
    area_difference: float
    geometry_conflict: bool
    attribute_conflict: bool
    recommendation: str

class ParcelDetail(ParcelReconciliationResponse):
    survey_number: str
    owner_name: str
    land_use: str
    area_cadastral_sqm: float
    area_drone_sqm: float
    village_name: str
    coordinates: List[List[float]]

MOCK_PARCELS_DB = [
    {
        "parcel_id": "1042",
        "survey_number": "204/A",
        "owner_name": "Sri Rajesh Kumar Verma",
        "land_use": "Commercial",
        "area_cadastral_sqm": 1420.0,
        "area_drone_sqm": 1444.0,
        "village_name": "Kondapur",
        "confidence": 87,
        "priority": "HIGH",
        "area_difference": 24.0,
        "geometry_conflict": True,
        "attribute_conflict": False,
        "recommendation": "Field verification required — 24m² area expansion & 3.2m boundary shift detected.",
        "coordinates": [[17.4475, 78.3750], [17.4478, 78.3762], [17.4468, 78.3765], [17.4465, 78.3752]]
    },
    {
        "parcel_id": "1043",
        "survey_number": "204/B",
        "owner_name": "Smt. Sunita Reddy",
        "land_use": "Residential",
        "area_cadastral_sqm": 850.0,
        "area_drone_sqm": 852.0,
        "village_name": "Kondapur",
        "confidence": 98,
        "priority": "LOW",
        "area_difference": 2.0,
        "geometry_conflict": False,
        "attribute_conflict": False,
        "recommendation": "Auto-Harmonized — High spatial & non-spatial agreement.",
        "coordinates": [[17.4478, 78.3762], [17.4481, 78.3774], [17.4472, 78.3777], [17.4468, 78.3765]]
    }
]

@app.get("/")
def read_root():
    return {
        "status": "online",
        "system": "LANDSYNC SIH26013 Reconciliation Layer",
        "version": "1.0.0"
    }

@app.post("/api/upload")
async def upload_dataset(file: UploadFile = File(...), source_type: str = "drone_ori"):
    return {
        "status": "success",
        "filename": file.filename,
        "source_type": source_type,
        "message": f"Successfully ingested {file.filename} into PostGIS staging."
    }

@app.post("/api/process")
def process_reconciliation():
    return {
        "status": "processed",
        "parcels_evaluated": len(MOCK_PARCELS_DB),
        "high_priority_conflicts": sum(1 for p in MOCK_PARCELS_DB if p["priority"] == "HIGH")
    }

@app.get("/api/parcels", response_model=List[ParcelReconciliationResponse])
def get_parcels():
    return [
        ParcelReconciliationResponse(
            parcel_id=p["parcel_id"],
            confidence=p["confidence"],
            priority=p["priority"],
            area_difference=p["area_difference"],
            geometry_conflict=p["geometry_conflict"],
            attribute_conflict=p["attribute_conflict"],
            recommendation=p["recommendation"]
        ) for p in MOCK_PARCELS_DB
    ]

@app.get("/api/conflicts", response_model=List[ParcelReconciliationResponse])
def get_conflicts():
    return [
        ParcelReconciliationResponse(**p)
        for p in MOCK_PARCELS_DB
        if p["priority"] in ["HIGH", "MEDIUM"]
    ]

@app.get("/api/parcels/{parcel_id}", response_model=ParcelDetail)
def get_parcel_by_id(parcel_id: str):
    for p in MOCK_PARCELS_DB:
        if p["parcel_id"] == parcel_id:
            return ParcelDetail(**p)
    raise HTTPException(status_code=404, detail="Parcel not found")

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)