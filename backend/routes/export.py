from fastapi import APIRouter, Depends, HTTPException, Response
from fastapi import Query
from typing import Optional
from database import get_db
from services.landsync_service import get_all_parcels
from routes.parcels import _ensure_loaded
import json

router = APIRouter(tags=["export"])

def generate_geojson(parcels: list):
    features = []
    for p in parcels:
        geom = p.get("boundaries", {}).get("cadastral")
        if not geom: continue
        features.append({
            "type": "Feature",
            "geometry": geom,
            "properties": {
                "parcel_id": p.get("parcel_id"),
                "confidence": p.get("confidence"),
                "priority": p.get("priority"),
                "area_difference": p.get("area_difference"),
                "geometry_conflict": p.get("geometry_conflict"),
                "attribute_conflict": p.get("attribute_conflict"),
                "recommendation": p.get("recommendation"),
                "match_status": p.get("match_status"),
            }
        })
    return {"type": "FeatureCollection", "features": features}

@router.get("/api/export")
async def export_dataset(dataset_id: str = Query(...)):
    try:
        _ensure_loaded()
        parcels = get_all_parcels()
        geojson = generate_geojson(parcels)
        content = json.dumps(geojson)
        return Response(
            content=content,
            media_type="application/geo+json",
            headers={"Content-Disposition": f"attachment; filename=landsync_export_{dataset_id}.geojson"}
        )
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Export failed: {str(e)}")
