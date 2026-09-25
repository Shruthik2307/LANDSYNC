# LANDSYNC — single-service Railway deployment (FastAPI backend + Vite SPA)
# Railway injects $PORT at runtime; the app binds 0.0.0.0:$PORT.
# FastAPI serves all /api/* routes AND the built React SPA from one origin.

# ── Stage 1: build the React frontend ─────────────────────────────────────
FROM node:20-slim AS frontend-build
WORKDIR /build

COPY package.json package-lock.json ./
RUN npm ci --no-audit --no-fund

COPY index.html vite.config.js postcss.config.js ./
# tailwind.config.js is optional — skip silently if missing
COPY tailwind.config.js* ./
COPY src ./src
COPY public ./public
COPY contract ./contract

# Accept CARTO API key as a build argument so it is baked into the bundle.
# Pass via Railway "Build Variables" as VITE_CARTO_API_KEY.
ARG VITE_CARTO_API_KEY="cb1_3jja_1_c1643a41b30964720658c0ac"
ARG VITE_API_BASE_URL=""
ARG VITE_ENABLE_SATELLITE_OVERLAY="true"
ENV VITE_CARTO_API_KEY=$VITE_CARTO_API_KEY \
    VITE_API_BASE_URL=$VITE_API_BASE_URL \
    VITE_ENABLE_SATELLITE_OVERLAY=$VITE_ENABLE_SATELLITE_OVERLAY

RUN npm run build

# ── Stage 2: Python runtime — backend + engine + ML model + frontend dist ─
FROM python:3.11-slim

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1 \
    LANDSYNC_SERVE_FRONTEND=1 \
    DEMO_FIXTURE_MODE=true

# System libraries: libGL (OpenCV), libglib2.0 (OpenCV), libgomp1 (scikit-learn)
RUN apt-get update && apt-get install -y --no-install-recommends \
        libgl1 libglib2.0-0 libgomp1 \
    && rm -rf /var/lib/apt/lists/*

# Install Python deps first (better layer caching)
COPY backend/requirements.txt /tmp/requirements.txt
RUN pip install --no-cache-dir -r /tmp/requirements.txt

WORKDIR /app

# Copy application source
COPY backend ./backend
COPY engine ./engine
COPY data ./data
COPY models ./models

# Copy the built Vite bundle
COPY --from=frontend-build /build/dist ./frontend-dist

WORKDIR /app/backend

# Expose default port (Railway overrides with $PORT at runtime)
EXPOSE 8000

# Railway injects PORT — bind to it. Falls back to 8000 for local Docker runs.
CMD ["sh", "-c", "uvicorn main:app --host 0.0.0.0 --port ${PORT:-8000} --workers 1"]
