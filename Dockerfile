# LANDSYNC — single-service deployment (FastAPI backend + built frontend)
# Built cloud-side by Render; no local Docker required.
# The FastAPI app serves the Vite bundle (SPA fallback) and all /api routes
# from one origin, so the deployed site needs no CORS or separate URL.

# ── Stage 1: build the frontend ───────────────────────────────────────────
FROM node:20-slim AS frontend-build
WORKDIR /build
COPY package.json package-lock.json ./
RUN npm ci --no-audit --no-fund
COPY index.html vite.config.js tailwind.config.js postcss.config.js ./
COPY src ./src
COPY public ./public
COPY contract ./contract
# Boot in LIVE mode: the API is same-origin (/api) on the unified service.
# Demo fixture stays one click away via the header toggle.
RUN npm run build

# ── Stage 2: Python runtime with backend + engine + frontend bundle ───────
FROM python:3.11-slim

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1 \
    LANDSYNC_SERVE_FRONTEND=1

# OpenCV needs libGL/libglib; scikit-learn needs libgomp.
RUN apt-get update && apt-get install -y --no-install-recommends \
        libgl1 libglib2.0-0 libgomp1 \
    && rm -rf /var/lib/apt/lists/*

COPY backend/requirements.txt /tmp/requirements.txt
RUN pip install -r /tmp/requirements.txt

WORKDIR /app
COPY backend ./backend
COPY engine ./engine
COPY data ./data
COPY models ./models
COPY --from=frontend-build /build/dist ./frontend-dist

WORKDIR /app/backend

# Render injects PORT; run the uvicorn CLI (main.py's __main__ hardcodes 8000).
EXPOSE 8000
CMD ["sh", "-c", "uvicorn main:app --host 0.0.0.0 --port ${PORT:-8000}"]
