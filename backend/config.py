"""Configuration settings for LANDSYNC backend"""
import os
from pathlib import Path

# Base paths
BASE_DIR = Path(__file__).resolve().parent
UPLOAD_DIR = BASE_DIR / "uploads"
DATA_DIR = BASE_DIR.parent / "data"

# Create necessary directories
UPLOAD_DIR.mkdir(exist_ok=True)
DATA_DIR.mkdir(exist_ok=True)

# Database configuration
DATABASE_URL = os.getenv(
    "DATABASE_URL",
    "postgresql://landsync:landsync@localhost:5432/landsync"
)

# API Configuration
API_VERSION = "1.0.0"
API_TITLE = "LANDSYNC AI Geospatial Reconciliation API"
API_DESCRIPTION = "SIH26013 Multi-Source Geospatial Harmonization & Confidence Engine"

# CORS settings
CORS_ORIGINS = os.getenv("CORS_ORIGINS", "*").split(",")

# File upload settings
MAX_UPLOAD_SIZE = 100 * 1024 * 1024  # 100MB
ALLOWED_EXTENSIONS = {".geojson", ".json", ".shp", ".zip", ".kml"}

# Processing settings
CONFIDENCE_THRESHOLD_HIGH = 90
CONFIDENCE_THRESHOLD_MEDIUM = 75
AREA_DIFFERENCE_THRESHOLD = 5.0  # square meters

# Satellite tile settings
SATELLITE_TILE_CACHE_DIR = BASE_DIR / "tile_cache"
SATELLITE_TILE_CACHE_DIR.mkdir(exist_ok=True)
SATELLITE_TILE_PROVIDERS = {
    "sentinel": "https://tiles.maps.eox.at/wms",
    "esri": "https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}"
}
