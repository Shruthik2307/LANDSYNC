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
import os
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

from config import settings, CORS_ORIGINS_LIST
from fastapi import FastAPI, HTTPException, Response
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse

# ── New engine-backed route modules ───────────────────────────────────────
from routes.health import router as health_router
from services.landsync_service import get_dataset_info, is_loaded
from routes.upload import router as upload_router
from routes.process import router as process_router
from routes.parcels import router as parcels_router
from routes.conflicts import router as conflicts_router
from routes.imagery import router as imagery_router
from routes.imagery_info import router as imagery_info_router
from routes.auth import router as auth_router
from routes.ml import router as ml_router
from routes.model_info import router as model_info_router
from routes.provenance import router as provenance_router
from routes.labeling import router as labeling_router
from routes.export import router as export_router
from routes.tgrac import router as tgrac_router




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
_cors_allow_all = "*" in CORS_ORIGINS_LIST
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"] if _cors_allow_all else CORS_ORIGINS_LIST,
    allow_credentials=not _cors_allow_all,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ── Register engine-backed routes ─────────────────────────────────────────
app.include_router(health_router)
app.include_router(upload_router)
app.include_router(process_router)
app.include_router(parcels_router)
app.include_router(conflicts_router)
app.include_router(imagery_router)
app.include_router(imagery_info_router)
app.include_router(auth_router)
app.include_router(ml_router)
app.include_router(model_info_router)
app.include_router(provenance_router)
app.include_router(labeling_router)
app.include_router(export_router)
app.include_router(tgrac_router)

# ── Satellite proxy (kept from original backend) ──────────────────────────
try:
    from satellite import get_satellite_tile
    _SATELLITE_AVAILABLE = True
except ImportError:  # pragma: no cover
    _SATELLITE_AVAILABLE = False




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

_SERVE_FRONTEND = os.getenv("LANDSYNC_SERVE_FRONTEND", "").lower() in {"1", "true", "yes"}

@app.get("/health")
def legacy_health():
    """Lightweight liveness + engine readiness check.

    Reports whether the server is alive, the reconciliation engine has data
    loaded, and the expected parcel count. Exposes no secrets.
    """
    loaded = is_loaded()
    parcel_count = get_dataset_info().get("reconciled_parcel_count", 0) if loaded else 0
    return {
        "status": "healthy" if loaded else "starting",
        "service": "landsync-backend",
        "engine": "loaded" if loaded else "unavailable",
        "parcel_count": parcel_count,
    }


if not _SERVE_FRONTEND:
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
# Optional: serve the built frontend (single-service deployment on Render).
# Enabled via LANDSYNC_SERVE_FRONTEND=1 and a Docker build stage that puts
# the Vite bundle at /app/frontend-dist. Registered LAST so every API route,
# /docs and /openapi.json keep precedence.
# ---------------------------------------------------------------------------

_default_dist = (
    _PROJECT_ROOT / "frontend-dist"
    if (_PROJECT_ROOT / "frontend-dist").is_dir()
    else _PROJECT_ROOT / "dist"
)
_FRONTEND_DIST = Path(os.getenv("LANDSYNC_FRONTEND_DIST", str(_default_dist)))

if _SERVE_FRONTEND:
    if _FRONTEND_DIST.is_dir():
        assets_dir = _FRONTEND_DIST / "assets"
        if assets_dir.is_dir():
            app.mount("/assets", StaticFiles(directory=assets_dir), name="assets")

        @app.get("/{full_path:path}", include_in_schema=False)
        async def spa_fallback(full_path: str):
            """Serve real files, else index.html for SPA client-side routes."""
            if full_path.startswith("api/"):
                raise HTTPException(status_code=404, detail="Not Found")
            candidate = (_FRONTEND_DIST / full_path).resolve()
            if full_path and candidate.is_file() and str(candidate).startswith(str(_FRONTEND_DIST.resolve())):
                return FileResponse(candidate)
            return FileResponse(_FRONTEND_DIST / "index.html")

        logger.info("Serving frontend bundle from %s", _FRONTEND_DIST)
    else:
        logger.warning(
            "LANDSYNC_SERVE_FRONTEND is set but %s does not exist — API-only mode.",
            _FRONTEND_DIST,
        )


# ---------------------------------------------------------------------------
# Startup: pre-load the sample dataset so the first API call is fast
# ---------------------------------------------------------------------------

@app.on_event("startup")
# Startup preload of synthetic fixtures is gated on DEMO_FIXTURE_MODE — see
# startup_event() below.
async def startup_event():
    """Pre-load the sample data on server startup (demo mode only).

    Synthetic data/sample/* fixtures are auto-loaded ONLY when
    DEMO_FIXTURE_MODE=true. In production (DEMO_FIXTURE_MODE=false) startup
    performs NO synthetic preload — the API reports REAL_DATA_UNAVAILABLE
    until a real dataset is uploaded and processed.
    """
    logger.info("=" * 60)
    logger.info("LANDSYNC Backend starting up …")
    logger.info("=" * 60)
    # ---- Production model validation (spec §22): verify loudly -----------
    try:
        from services.model_info import get_registry

        registry = get_registry()
        if registry.available:
            logger.info("✓ ML model artifact validated: %s", registry.info().get("model_version"))
        else:
            logger.info("ℹ ML model: %s — deterministic GIS evidence remains authoritative.", registry.reason)
    except Exception as exc:
        logger.error("✗ Model registry validation errored: %s", exc)
    if not settings.DEMO_FIXTURE_MODE:
        logger.info(
            "DEMO_FIXTURE_MODE=false (production): skipping synthetic sample "
            "preload. API reports REAL_DATA_UNAVAILABLE until real data is "
            "uploaded (POST /api/upload) and processed (POST /api/process)."
        )
        logger.info("=" * 60)
        return
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
        logger.info("  Engine CRS    : EPSG:3857 (metric)")
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
