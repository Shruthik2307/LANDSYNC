"""
LANDSYNC — SIH26013 FastAPI Backend
=====================================
Main application entry point.

Route registration
------------------
New engine-backed routes (Phase 1):
    GET  /api/health           → routes/health.py
    POST /api/upload           → routes/upload.py
    POST /api/process          → routes/process.py
    GET  /api/parcels          → routes/parcels.py
    GET  /api/parcels/{id}     → routes/parcels.py
    GET  /api/conflicts        → routes/conflicts.py

Kept from original backend:
    GET  /api/satellite-tile/{z}/{x}/{y}  → satellite.py
    GET  /health               → simple health check (legacy)
    GET  /                     → system status (legacy)

The legacy SQLAlchemy-backed routes (database.py, services.py) remain
importable but are not re-registered here to avoid route conflicts.
The new engine-backed routes take precedence for all /api/* paths.
"""

from __future__ import annotations

import logging
import sys
from pathlib import Path

# ---------------------------------------------------------------------------
# sys.path bootstrap — ensure project root is importable as a package root
# so that `import engine` and `import services` both resolve correctly when
# uvicorn is started from any working directory.
# ---------------------------------------------------------------------------
_BACKEND_DIR = Path(__file__).resolve().parent
_PROJECT_ROOT = _BACKEND_DIR.parent
for _p in (_PROJECT_ROOT, _BACKEND_DIR):
    if str(_p) not in sys.path:
        sys.path.insert(0, str(_p))

from fastapi import FastAPI, Response
from fastapi.middleware.cors import CORSMiddleware

# ── New engine-backed route modules ───────────────────────────────────────
from routes.health import router as health_router
from routes.upload import router as upload_router
from routes.process import router as process_router
from routes.parcels import router as parcels_router
from routes.conflicts import router as conflicts_router

# ── Satellite proxy (kept from original backend) ──────────────────────────
try:
    from satellite import get_satellite_tile
    _SATELLITE_AVAILABLE = True
except ImportError:  # pragma: no cover
    _SATELLITE_AVAILABLE = False

# ── Service for startup auto-load ─────────────────────────────────────────
from services.landsync_service import load_data

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# FastAPI application
# ---------------------------------------------------------------------------

app = FastAPI(
    title="LANDSYNC AI Geospatial Reconciliation API",
    description=(
        "SIH26013 — Multi-source land and cadastral reconciliation backend. "
        "Powered by the LANDSYNC engine (GeoPandas + Shapely + pyproj)."
    ),
    version="1.0.0",
    docs_url="/docs",
    openapi_url="/openapi.json",
)

# ── CORS ──────────────────────────────────────────────────────────────────
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ── Register engine-backed routes ─────────────────────────────────────────
app.include_router(health_router)
app.include_router(upload_router)
app.include_router(process_router)
app.include_router(parcels_router)
app.include_router(conflicts_router)


# ---------------------------------------------------------------------------
# Satellite tile proxy (kept from original backend)
# ---------------------------------------------------------------------------

if _SATELLITE_AVAILABLE:
    @app.get("/api/satellite-tile/{z}/{x}/{y}")
    async def satellite_tile_proxy(z: int, x: int, y: int):
        """Proxy satellite tile imagery from upstream providers."""
        try:
            tile_data = await get_satellite_tile(z, x, y)
            if tile_data is None:
                return Response(status_code=204)
            return Response(content=tile_data, media_type="image/png")
        except Exception as exc:
            logger.error("Satellite tile error %d/%d/%d: %s", z, x, y, exc)
            return Response(status_code=204)


# ---------------------------------------------------------------------------
# Legacy routes (kept for backwards compatibility)
# ---------------------------------------------------------------------------

@app.get("/health")
def legacy_health():
    """Legacy simple health check (kept for backwards compatibility)."""
    return {"status": "healthy", "service": "landsync-backend"}


@app.get("/")
def root():
    """Root — links to API docs."""
    return {
        "service": "LANDSYNC SIH26013 Reconciliation API",
        "version": "1.0.0",
        "docs": "/docs",
        "health": "/api/health",
        "parcels": "/api/parcels",
        "conflicts": "/api/conflicts",
    }


# ---------------------------------------------------------------------------
# Startup: pre-load the sample dataset so the first API call is fast
# ---------------------------------------------------------------------------

@app.on_event("startup")
async def startup_event():
    """Pre-load the sample data on server startup."""
    logger.info("=" * 60)
    logger.info("LANDSYNC Backend starting up …")
    logger.info("=" * 60)
    try:
        info = load_data()
        logger.info(
            "✓ Engine loaded: %d parcels reconciled (cadastral=%d, municipal=%d)",
            info["reconciled_parcel_count"],
            info["cadastral_feature_count"],
            info["municipal_feature_count"],
        )
        logger.info("  Cadastral CRS : %s", info["cadastral_crs"])
        logger.info("  Municipal CRS : %s", info["municipal_crs"])
        logger.info("  Engine CRS    : %s (EPSG:3857 — metric)", info["engine_crs"])
    except FileNotFoundError as exc:
        logger.warning(
            "⚠ Sample data not found at startup: %s\n"
            "  GET /api/parcels will attempt to load on first request.",
            exc,
        )
    except Exception as exc:
        logger.error("✗ Engine pre-load failed at startup: %s", exc)
        logger.error(
            "  GET /api/parcels will re-attempt load on first request."
        )
    logger.info("=" * 60)


# ---------------------------------------------------------------------------
# Dev entry point
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "main:app",
        host="0.0.0.0",
        port=8000,
        reload=True,
        log_level="info",
    )
