# LANDSYNC Backend

FastAPI backend for SIH26013 — Multi-Source Land and Cadastral Reconciliation System.

## Architecture

```
backend/
├── main.py                      # FastAPI app, route registration, startup auto-load
├── requirements.txt             # Python dependencies
├── config.py                    # Legacy config (CORS, upload limits, etc.)
├── models.py                    # Pydantic models (legacy + new)
├── database.py                  # SQLAlchemy/SQLite (kept for satellite proxy)
├── services.py                  # Legacy processing helpers
├── satellite.py                 # Satellite tile proxy
├── routes/
│   ├── health.py                # GET  /api/health
│   ├── upload.py                # POST /api/upload
│   ├── process.py               # POST /api/process
│   ├── parcels.py               # GET  /api/parcels, GET /api/parcels/{id}
│   └── conflicts.py             # GET  /api/conflicts
├── services/
│   └── landsync_service.py      # Core: loads GeoJSON → runs engine → caches results
└── tests/
    ├── conftest.py              # pytest fixtures (TestClient)
    └── test_backend.py          # Backend integration tests
```

## Relationship to Core Engine

```
backend/
  └── services/landsync_service.py
        ├── loads data/sample/cadastral.geojson  (GeoPandas, EPSG:4326)
        ├── loads data/sample/municipal.geojson  (GeoPandas, EPSG:4326)
        └── calls engine/pipeline.run_reconciliation()
                 ├── engine/crs.py      → reprojects both GDFs to EPSG:3857
                 ├── engine/matching.py → pairs parcels by ID (+ spatial fallback)
                 └── engine/conflicts.py → scores each pair (IoU, area, attributes)
```

The backend does **not** duplicate any GIS logic. All geometry operations, CRS
handling, and conflict scoring live exclusively in `engine/`.

## Setup

### 1. Install Dependencies

```bash
cd backend
pip install -r requirements.txt
```

> **Windows users**: If `geopandas` or `fiona` fail to install via pip,
> install them from the [unofficial Windows binaries](https://www.lfd.uci.edu/~gohlke/pythonlibs/)
> or use conda:
> ```bash
> conda install geopandas fiona shapely pyproj
> pip install fastapi uvicorn[standard] python-multipart aiofiles aiohttp pydantic pytest httpx
> ```

### 2. Configure Environment (Optional)

```bash
cp .env.example .env
# Edit .env if needed (CORS_ORIGINS, DATABASE_URL, etc.)
```

### 3. Run the Server

```bash
# From the LANDSYNC project root:
cd backend
uvicorn main:app --reload --host 0.0.0.0 --port 8000
```

Or from the project root:
```bash
uvicorn backend.main:app --reload --port 8000
```

On startup the server will:
1. Load `data/sample/cadastral.geojson` and `data/sample/municipal.geojson`
2. Run `engine.pipeline.run_reconciliation()` (CRS → EPSG:3857, match, score)
3. Cache 25 reconciled parcel records in memory

### 4. Connect the Frontend

```bash
# In the LANDSYNC project root, set the API base URL:
echo "VITE_API_BASE_URL=http://localhost:8000" > .env

# Start the frontend dev server:
npm run dev
```

The Vite dev server already proxies `/api` → `http://127.0.0.1:8000` (see `vite.config.js`).

## API Endpoints

| Method | Path                   | Description                                    |
|--------|------------------------|------------------------------------------------|
| GET    | `/api/health`          | Backend + engine status, parcel count, CRS     |
| POST   | `/api/upload`          | Upload a GeoJSON dataset                       |
| POST   | `/api/process`         | Trigger reconciliation, reload cache           |
| GET    | `/api/parcels`         | All 25 reconciled parcels                      |
| GET    | `/api/parcels/{id}`    | Single parcel by parcel_id                     |
| GET    | `/api/conflicts`       | Conflict parcels only, sorted by priority      |
| GET    | `/api/satellite-tile/{z}/{x}/{y}` | Satellite tile proxy                |
| GET    | `/health`              | Legacy health check                            |
| GET    | `/docs`                | Swagger UI                                     |

### `GET /api/health`

```json
{
  "status": "ok",
  "service": "landsync-backend",
  "version": "1.0.0",
  "engine": "loaded",
  "parcel_count": 25,
  "cadastral_crs": "EPSG:4326",
  "municipal_crs": "EPSG:4326",
  "engine_crs": "EPSG:3857",
  "cadastral_features": 25,
  "municipal_features": 25
}
```

### `GET /api/parcels` — Parcel Schema

```json
{
  "parcel_id": "HYD-REV-1000",
  "confidence": 72,
  "priority": "MEDIUM",
  "area_difference": -123.45,
  "geometry_conflict": true,
  "attribute_conflict": false,
  "duplicate_id": false,
  "recommendation": "Geometry conflict detected (IoU=0.847, area delta=123.5 m² / 5.2%) — verify boundary source data.",
  "boundaries": {
    "cadastral": { "type": "Polygon", "coordinates": [[...]] },
    "drone_ori":  { "type": "Polygon", "coordinates": [[...]] }
  }
}
```

> `boundaries.drone_ori` is present only when `geometry_conflict == true`.
> Municipal survey data fills the `drone_ori` role in Phase 1.

## CRS Handling

| Stage | CRS | Why |
|-------|-----|-----|
| Source GeoJSON files | EPSG:4326 (WGS84) | Standard GeoJSON format |
| Engine processing | EPSG:3857 (Web Mercator) | Metric area in m² (`area_difference`) |
| API response `boundaries` | EPSG:4326 | Frontend map renders WGS84 coordinates |

The engine (`engine/crs.py`) handles reprojection internally using `CRSManager.reproject()`.
The service (`services/landsync_service.py`) preserves original EPSG:4326 geometries
for the `boundaries` response field.

## Running Tests

```bash
cd backend
pytest tests/ -v
```

Expected output: all tests pass, including:
- `test_health_engine_loaded_after_startup`
- `test_municipal_geojson_has_25_features`
- `test_parcels_count` (25 parcels)
- `test_unknown_parcel_returns_404`
- `test_conflicts_sorted_high_first`
- `test_valid_upload_has_dataset_id`
- `test_invalid_json_returns_400`

## Troubleshooting

### Port already in use

```bash
# Windows
netstat -ano | findstr :8000
taskkill /PID <pid> /F
```

### CORS errors from frontend

Ensure `CORS_ORIGINS` in `config.py` includes your frontend URL, or the default `*` allows all.

### GeoPandas / Fiona import errors on Windows

```bash
conda install -c conda-forge geopandas
```

### Engine returns 0 parcels

Check that `data/sample/cadastral.geojson` and `data/sample/municipal.geojson` both exist
and have matching `parcel_id` values. Both files must contain 25 features with IDs
`HYD-REV-1000` through `HYD-REV-1024`.

## Phase 2 Roadmap

- Accept a second uploaded file as the alternative source (replaces hardcoded municipal path)
- Stream processing status updates via Server-Sent Events
- PostgreSQL persistence for multi-session result storage
- PostGIS-backed spatial queries for large datasets
