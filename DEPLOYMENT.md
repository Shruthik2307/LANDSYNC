# LANDSYNC (SIH26013) — Production Deployment Guide

## Overview

LANDSYNC is an automated geospatial cadastral and municipal boundary reconciliation platform engineered for SIH26013.

The application architecture supports two primary deployment topologies:
1. **Unified Single-Service (Production Recommended):** FastAPI serves both the REST API (`/api/*`) and the compiled Vite SPA bundle from a single port and origin. Zero CORS configuration required.
2. **Decoupled Development:** FastAPI backend running on port 8000 + Vite development server running on port 5173 with proxy configuration.

---

## 1. Unified Single-Container Deployment (Docker / Cloud Run / Railway / Render)

### Architecture
- **Stage 1 (Builder):** Node 20-slim compiles the React/Vite application into static production assets (`/build/dist`).
- **Stage 2 (Runtime):** Python 3.11-slim packages FastAPI, GIS libraries (GDAL/Shapely/GeoPandas/pyproj), the pre-trained production ML model (`models/` and `backend/models/`), and the built frontend bundle (`frontend-dist/`).

### Container Build & Run

```bash
# Build the unified production container
docker build -t landsync:production .

# Run the container (default port 8000)
docker run -p 8000:8000 -e LANDSYNC_SERVE_FRONTEND=1 landsync:production
```

Once running:
- Web Application: `http://localhost:8000/`
- API Health Check: `http://localhost:8000/api/health`
- Interactive Swagger Docs: `http://localhost:8000/docs`
- ML Model Status: `http://localhost:8000/api/ml/status`

---

## 2. Environment Variables Reference

| Variable | Default | Purpose |
|---|---|---|
| `PORT` | `8000` | HTTP port for Uvicorn server |
| `LANDSYNC_SERVE_FRONTEND` | `1` (in Docker) | Set to `1` or `true` to enable static SPA serving from FastAPI |
| `LANDSYNC_FRONTEND_DIST` | `/app/frontend-dist` | Filesystem path to compiled frontend assets |
| `DEMO_FIXTURE_MODE` | `true` | If `true`, preloads sample Hyderabad parcels for offline demo |
| `DATABASE_URL` | `sqlite:///./landsync.db` | SQLAlchemy database connection string (SQLite or PostgreSQL) |
| `SECRET_KEY` | *(auto-generated)* | Key for session authentication and token signing |
| `CORS_ORIGINS` | `*` | Allowed CORS origins for API requests |
| `VITE_API_BASE_URL` | `""` | Frontend API base URL (empty string enables same-origin relative URLs) |

---

## 3. Local Development Startup

### Prerequisites
- Python 3.11+ (tested on Python 3.13)
- Node.js 18+ (tested on Node 20)
- npm

### Step 1: Install Dependencies
```bash
# Frontend
npm ci

# Backend
cd backend
pip install -r requirements.txt
cd ..
```

### Step 2: Start Services

**Option A — Automated Launcher:**
```bash
# Windows
start.bat

# Linux / macOS
chmod +x start.sh
./start.sh
```

**Option B — Manual Terminals:**
```bash
# Terminal 1: Backend
cd backend
python -m uvicorn main:app --port 8000 --host 127.0.0.1 --reload

# Terminal 2: Frontend
npm run dev
```

---

## 4. Health Checks & Verification

Perform these curl or browser checks to verify deployment:

```bash
# 1. API Health & Engine Status
curl http://localhost:8000/api/health
# Response: {"status":"ok","engine":"loaded","parcel_count":25,"engine_crs":"EPSG:3857"}

# 2. ML Production Model Status
curl http://localhost:8000/api/ml/status
# Response: {"model_status":"OK","model_version":"rf-tgrac-v1.0.0-b1f6d178","accuracy":0.8571}

# 3. Parcel Queue
curl http://localhost:8000/api/parcels

# 4. Frontend Root
curl -I http://localhost:8000/
# Response: HTTP/1.1 200 OK (Content-Type: text/html)
```

---

## 5. Security & Isolation Safeguards

- **Zero Secret Leakage:** No private keys or cloud credentials hardcoded in repository or client bundle.
- **Path Isolation:** All model, data, and cache paths resolved dynamically relative to `__file__`. No absolute paths (`D:\...`) in production code.
- **Model Integrity Protection:** Anti-cheating guardrails (`scripts/check_ml_integrity.py`) enforce zero synthetic data contamination and independently verified model hashes.
