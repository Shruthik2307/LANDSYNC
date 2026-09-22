"""Pydantic models for API request/response validation"""
from pydantic import BaseModel, Field
from typing import List, Optional, Literal


class GeoJSONPolygon(BaseModel):
    """GeoJSON Polygon geometry"""
    type: Literal["Polygon"] = "Polygon"
    coordinates: List[List[List[float]]]


class ParcelBoundaries(BaseModel):
    """Parcel boundary geometries"""
    cadastral: GeoJSONPolygon
    drone_ori: Optional[GeoJSONPolygon] = None


class ParcelResponse(BaseModel):
    """Parcel data returned to frontend"""
    parcel_id: str
    confidence: int = Field(ge=0, le=100)
    priority: Literal["HIGH", "MEDIUM", "LOW"]
    area_difference: float
    geometry_conflict: bool
    attribute_conflict: bool
    duplicate_id: bool = False
    recommendation: str
    boundaries: ParcelBoundaries

    class Config:
        from_attributes = True


class UploadResponse(BaseModel):
    """Response from file upload"""
    dataset_id: str
    status: str = "success"
    filename: str
    message: Optional[str] = None


class ProcessRequest(BaseModel):
    """Request to start processing"""
    dataset_id: str


class ProcessResponse(BaseModel):
    """Response from process request"""
    job_status: Literal["queued", "processing", "complete", "failed"]
    dataset_id: str
    parcels_evaluated: Optional[int] = None
    high_priority_conflicts: Optional[int] = None
    message: Optional[str] = None


class SystemStatus(BaseModel):
    """System health check response"""
    status: str
    system: str
    version: str
    database_connected: bool
    total_parcels: int
    total_datasets: int
