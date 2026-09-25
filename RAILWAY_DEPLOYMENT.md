# LANDSYNC — Railway Deployment Guide
> SIH26013 · Production Release · Commit `2846361`

---

## ✅ Pre-Deployment Status

| Check | Status |
|---|---|
| React build (`npm run build`) | ✅ PASS — 2350 modules, 2.13s |
| Git commit | ✅ `2846361` pushed to `main` |
| Dockerfile | ✅ Railway-ready (`${PORT:-8000}`, `0.0.0.0`) |
| `railway.toml` | ✅ Created with healthcheck `/api/health` |
| `.dockerignore` | ✅ `.env` excluded — no secrets in build |
| ML model (`conflict_detector.pkl`) | ✅ In repo at `backend/models/` |
| `LANDSYNC_SERVE_FRONTEND=1` | ✅ Baked in Dockerfile ENV |
| No hardcoded localhost paths | ✅ Verified |

---

## 1. Railway Deployment Steps

### Step 1 — Log In to Railway

1. Go to **[https://railway.app](https://railway.app)**
2. Click **"Login"** → **"Login with GitHub"**
3. Authorize Railway to access your GitHub account

### Step 2 — Create New Project

1. Click **"New Project"**
2. Select **"Deploy from GitHub repo"**
3. Search for and select: **`Shruthik2307/LANDSYNC`**
4. Click **"Deploy Now"**

Railway will automatically detect the `Dockerfile` and `railway.toml` in the repo root.

### Step 3 — Set Environment Variables

In the Railway dashboard, go to your service → **"Variables"** tab and add:

| Variable | Value | Notes |
|---|---|---|
| `LANDSYNC_SERVE_FRONTEND` | `1` | FastAPI serves the React SPA |
| `DEMO_FIXTURE_MODE` | `true` | Enables demo data auto-load |
| `VITE_CARTO_API_KEY` | `cb1_3jja_1_c1643a41b30964720658c0ac` | Set as **Build Variable** |
| `PORT` | *(auto-injected by Railway)* | Do NOT set manually |

> **Important:** `VITE_CARTO_API_KEY` must be set as a **Build Variable** (not just a runtime variable) because Vite bakes env vars into the bundle at build time. In Railway: Variables tab → toggle "Build Variable" checkbox.

### Step 4 — Generate Public Domain

1. Go to your service → **"Settings"** tab → **"Networking"**
2. Click **"Generate Domain"**
3. Railway will assign: `https://landsync-production-<id>.up.railway.app`

### Step 5 — Trigger Deploy

If not already deploying, click **"Deploy"** on the main service page.
The first build takes 3-5 minutes (installing Python deps + npm build).

---

## 2. Required Environment Variables

```
# Runtime (set in Railway Variables tab)
LANDSYNC_SERVE_FRONTEND=1
DEMO_FIXTURE_MODE=true

# Build Variable (enable "Build Variable" toggle in Railway)
VITE_CARTO_API_KEY=cb1_3jja_1_c1643a41b30964720658c0ac

# Auto-injected by Railway — DO NOT SET
# PORT=<auto>
```

---

## 3. Health Check Endpoints

```
GET /api/health
Expected: {"status":"healthy","service":"landsync-backend","engine":"loaded",...}

GET /api/ml/status
Expected: {"loaded":true,"model_version":"rf-tgrac-v1.0.0-b1f6d178",...}

GET /docs
FastAPI interactive API documentation
```

---

## 4. Live URL

> Pending manual Railway login and domain generation.

Once deployed:
```
https://landsync-production-<id>.up.railway.app
```

---

## 5. Browser Smoke Test (Judge Demo Flow)

1. **Landing** → `https://<domain>/` → LANDSYNC hero page loads
2. **Explore Demo** → click "Explore Demo" → synthetic fixtures load
3. **Reconciliation Map** → CARTO dark basemap (no watermark)
4. **Select Parcel** → click any shape → Detail Panel opens
5. **GIS Metrics** → area delta, IoU, boundary shift visible
6. **ML Classification** → MATCH / MINOR / MAJOR + confidence score
7. **Minimize Panel** → press `M` → slim bar, full map visible
8. **Satellite** → enable satellite, zoom in — stays visible at any zoom
9. **Verify/Reject** → review buttons in Detail Panel work

---

## 6. Rollback Instructions

Via Railway dashboard:
1. Service → **Deployments** tab
2. Find previous deployment (commit `b1f22e1`)
3. Click "..." → **Redeploy**

Via Railway CLI:
```bash
railway login
railway link   # select LANDSYNC project
railway rollback
```

---

## 7. Troubleshooting

| Symptom | Fix |
|---|---|
| Map shows "API KEY REQUIRED" | Set `VITE_CARTO_API_KEY` as a **Build Variable** |
| `/` returns JSON not HTML | `LANDSYNC_SERVE_FRONTEND` not set |
| `/api/health` returns `starting` | Engine loading; wait 10s, check startup logs |
| ML model not loaded | Verify `backend/models/conflict_detector.pkl` in build |
| Build fails | Ensure Railway uses Dockerfile builder (check `railway.toml`) |
| Satellite disappears on zoom | Fixed in commit `2846361` |
| Detail panel blocks map | Press `M` or click minimize button |

---

## 8. Architecture

```
Railway Container (single service)
├── /app/backend/          FastAPI + uvicorn on $PORT
│   ├── main.py            Entry point: serves /api/* + SPA fallback
│   ├── models/            conflict_detector.pkl (RF classifier)
│   └── routes/            health, ml, parcels, upload, tgrac ...
├── /app/engine/           GIS reconciliation engine
├── /app/data/             Sample fixtures (DEMO_FIXTURE_MODE=true)
└── /app/frontend-dist/    Built React SPA
    ├── index.html
    └── assets/
```

---

## 9. ML Model Integrity (DO NOT MODIFY)

| Property | Value |
|---|---|
| File | `backend/models/conflict_detector.pkl` |
| Algorithm | Random Forest Classifier |
| Version | `rf-tgrac-v1.0.0-b1f6d178` |
| Training samples | 31 genuine human-reviewed TGRAC pairs |
| Class balance | 11 MATCH / 10 MINOR / 10 MAJOR |
| CV Accuracy | 95.00% ± 10% (5-fold stratified) |
| Held-out Accuracy | 85.71% (6/7) |
| Held-out Macro F1 | 84.13% |
