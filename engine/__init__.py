"""
engine — Core reconciliation pipeline modules.

Public API:
    CRSManager          : Reproject any GeoDataFrame to EPSG:3857.
    match_parcels       : Merge two GeoDataFrames on parcel_id with spatial fallback.
    evaluate_conflicts  : Score a matched parcel row and return the reconciliation dict.
"""

from engine.crs import CRSManager
from engine.matching import match_parcels
from engine.conflicts import evaluate_conflicts

__all__ = ["CRSManager", "match_parcels", "evaluate_conflicts"]
