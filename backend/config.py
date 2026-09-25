"""Configuration settings for LANDSYNC backend"""
import os
from pathlib import Path
from pydantic_settings import BaseSettings, SettingsConfigDict

class Settings(BaseSettings):
    # Base paths
    BASE_DIR: Path = Path(__file__).resolve().parent
    UPLOAD_DIR: Path = Path(__file__).resolve().parent / "uploads"
    DATA_DIR: Path = Path(__file__).resolve().parent.parent / "data"

    # Database configuration
    # Defaults to a local SQLite file for development. For production set
    # DATABASE_URL to PostgreSQL with PostGIS (see .env.example).
    DATABASE_URL: str = "sqlite:///./landsync.db"

    # API Configuration
    API_VERSION: str = "1.0.0"
    API_TITLE: str = "LANDSYNC AI Geospatial Reconciliation API"
    API_DESCRIPTION: str = "SIH26013 Multi-Source Geospatial Harmonization & Confidence Engine"

    # CORS settings
    CORS_ORIGINS: str = "*"

    # File upload settings
    MAX_UPLOAD_SIZE: int = 500 * 1024 * 1024  # 500MB
    ALLOWED_EXTENSIONS: set = {".geojson", ".json", ".shp", ".zip", ".kml"}

    # Processing settings
    CONFIDENCE_THRESHOLD_HIGH: int = 90
    CONFIDENCE_THRESHOLD_MEDIUM: int = 75
    AREA_DIFFERENCE_THRESHOLD: float = 5.0  # square meters

    # Demo-fixture isolation (spec §7). The bundled data/sample/* GeoJSON files
    # are SYNTHETIC demonstration fixtures. They may auto-load only when this
    # flag is true (development, CI, deterministic UI testing, offline demos).
    # With DEMO_FIXTURE_MODE=false (production), the backend never silently
    # loads synthetic sample parcels: if no real dataset has been uploaded,
    # the API reports a REAL_DATA_UNAVAILABLE state instead. Set
    # DEMO_FIXTURE_MODE=false in the Railway/production environment.
    DEMO_FIXTURE_MODE: bool = True

    # Satellite tile settings
    SATELLITE_TILE_CACHE_DIR: Path = Path(__file__).resolve().parent / "tile_cache"
    SATELLITE_TILE_PROVIDERS: dict = {
        "sentinel": "https://tiles.maps.eox.at/wms",
        "esri": "https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}"
    }

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

settings = Settings()

# Maintain directory creation at module level
settings.UPLOAD_DIR.mkdir(exist_ok=True)
settings.DATA_DIR.mkdir(exist_ok=True)
settings.SATELLITE_TILE_CACHE_DIR.mkdir(exist_ok=True)

# Helper for CORS origins list
CORS_ORIGINS_LIST = [origin.strip() for origin in settings.CORS_ORIGINS.split(",") if origin.strip()]
