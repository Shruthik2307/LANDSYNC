# LANDSYNC backend — FastAPI + GeoPandas + Rasterio + scikit-learn
# Built cloud-side by Render (no local Docker required).
FROM python:3.11-slim

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1

# OpenCV needs libGL/libglib; scikit-learn needs libgomp.
# rasterio/fiona/pyproj manylinux wheels bundle their own GDAL/PROJ.
RUN apt-get update && apt-get install -y --no-install-recommends \
        libgl1 libglib2.0-0 libgomp1 \
    && rm -rf /var/lib/apt/lists/*

# Dependencies first for layer caching
COPY backend/requirements.txt /tmp/requirements.txt
RUN pip install -r /tmp/requirements.txt

# Full repo: backend/ + engine/ + data/sample/*.geojson + models
WORKDIR /app
COPY . /app

WORKDIR /app/backend

# Render injects PORT; default to 8000 for local runs.
# NOTE: we run the uvicorn CLI (not `python main.py`) because main.py's
# __main__ block hardcodes port 8000 and reload=True.
EXPOSE 8000
CMD ["sh", "-c", "uvicorn main:app --host 0.0.0.0 --port ${PORT:-8000}"]
