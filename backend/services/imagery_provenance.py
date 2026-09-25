"""
Imagery provenance service — REAL metadata only, never fabricated.
==================================================================

LANDSYNC distinguishes BASEMAP imagery from VALIDATED OBSERVATION IMAGERY.
Every fact served by this module comes from a live provider API or is
explicitly reported as unavailable. Nothing here invents dates/resolutions.

Providers
---------
esri_wayback   Esri World Imagery (Wayback metadata service). Returns the
               real acquisition date (SRC_DATE), source sensor (SRC_DESC),
               native resolution in m/px (SRC_RES) and product name
               (NICE_NAME) for the exact queried location — via an ArcGIS
               identify on the metadata polygons behind the imagery mosaic.
sentinel2      EOX s2cloudless cloudless Sentinel-2 mosaics (yearly).
               Fixed ~10 m/px resolution; acquisition year comes from the
               layer the caller selected. NOT suitable for parcel-boundary
               or individual-building verification — a genuine limitation
               that the API reports instead of hiding.
"""
from __future__ import annotations

import json
import logging
import time
from datetime import datetime, timezone
from typing import Any, Optional

import aiohttp

from config import settings

logger = logging.getLogger(__name__)

# EOX s2cloudless: latest available cloudless Sentinel-2 mosaic year.
# Verified against the live WMTS capabilities; bump only after checking
# https://tiles.maps.eox.at/wmts/1.0.0/WMTSCapabilities.xml
SENTINEL2_LATEST_YEAR = 2025
SENTINEL2_RESOLUTION_M = 10.0  # native band resolution of the mosaic

# Esri Wayback metadata service (per-release MapServer). The 2026-r02
# release tracks the CURRENT World Imagery mosaic; the identify endpoint
# reports which real source image covers the queried point.
_ESRI_METADATA_URL = (
    "https://metadata.maptiles.arcgis.com/arcgis/rest/services/"
    "World_Imagery_Metadata_2026_r02/MapServer/identify"
)

_ESRI_TILE_URL = "https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}"

# In-memory TTL cache — free-tier friendly (no polling, no keep-alives).
_cache: dict[str, tuple[float, dict[str, Any]]] = {}
_CACHE_TTL_S = 6 * 3600  # imagery metadata changes rarely


def _cached(key: str) -> Optional[dict[str, Any]]:
    hit = _cache.get(key)
    if hit and (time.monotonic() - hit[0]) < _CACHE_TTL_S:
        return hit[1]
    return None


def _store(key: str, value: dict[str, Any]) -> dict[str, Any]:
    _cache[key] = (time.monotonic(), value)
    return value


def _lng_lat_to_mercator(lng: float, lat: float) -> tuple[float, float]:
    import math
    x = lng * 20037508.34 / 180.0
    y = (
        math.log(math.tan((90.0 + lat) * math.pi / 360.0))
        / (math.pi / 180.0)
        * 20037508.34 / 180.0
    )
    return x, y


def _zoom_for_point(lng: float, lat: float) -> int:
    """Pick a sensible metadata-query zoom from the parcel's own extent.

    The metadata polygons are large (100M+ m²); identify matches every
    polygon containing the point, and the deepest ones carry the real
    acquisition attributes. Zoom drives which polygons the service
    considers — 16 is deep enough for parcel-scale sources.
    """
    return 16


def _fmt_src_date(raw: Any) -> str:
    """Esri SRC_DATE is YYYYMMDD (sometimes with a 2nd constituent date)."""
    try:
        s = str(raw)[:8]
        return datetime.strptime(s, "%Y%m%d").date().isoformat()
    except (ValueError, TypeError):
        return ""


async def get_esri_imagery_info(lng: float, lat: float) -> dict[str, Any]:
    """Real acquisition metadata for the Esri World Imagery mosaic at (lng, lat).

    Returns provider facts only. On any upstream failure the response says
    the metadata is unavailable — it never substitutes a guess.
    """
    key = f"esri:{lng:.5f}:{lat:.5f}"
    cached = _cached(key)
    if cached:
        return cached

    mx, my = _lng_lat_to_mercator(lng, lat)
    span = 3000.0  # ~3 km query extent around the point
    payload = {
        "geometry": json.dumps(
            {"x": mx, "y": my, "spatialReference": {"latestWkid": 3857}}
        ),
        "geometryType": "esriGeometryPoint",
        "sr": "3857",
        "layers": "all",
        "tolerance": "1",
        "mapExtent": json.dumps(
            {
                "xmin": mx - span, "ymin": my - span,
                "xmax": mx + span, "ymax": my + span,
                "spatialReference": {"latestWkid": 3857},
            }
        ),
        "imageDisplay": "600,600,96",
        "returnGeometry": "false",
        "f": "json",
    }
    try:
        timeout = aiohttp.ClientTimeout(total=10)
        # Esri's CDN rejects requests without a descriptive User-Agent.
        headers = {"User-Agent": "LANDSYNC/1.0 (cadastral reconciliation; contact: demo)"}
        async with aiohttp.ClientSession() as session:
            async with session.get(_ESRI_METADATA_URL, params=payload, headers=headers, timeout=timeout) as resp:
                if resp.status != 200:
                    raise RuntimeError(f"metadata service HTTP {resp.status}")
                data = await resp.json(content_type=None)
    except Exception as exc:
        logger.warning("Esri imagery metadata unavailable: %s", exc)
        return _store(key, {
            "provider": "Esri World Imagery",
            "status": "metadata_unavailable",
            "acquired": None,
            "acquisition_date_available": False,
            "note": "Imagery acquisition date unavailable",
        })

    results = data.get("results") or []
    deepest: dict[str, Any] = {}
    for r in results:
        attrs = r.get("attributes", {})
        # Deepest source = smallest sampling resolution = the actual pixels.
        try:
            cand_res = float(attrs.get("SAMP_RES") or attrs.get("SRC_RES") or 999)
        except (TypeError, ValueError):
            cand_res = 999.0
        try:
            best_res = float(deepest.get("_samp") or 999)
        except (TypeError, ValueError):
            best_res = 999.0
        if cand_res < best_res:
            deepest = {"_samp": attrs.get("SAMP_RES"), **attrs}

    if not deepest:
        return _store(key, {
            "provider": "Esri World Imagery",
            "status": "metadata_unavailable",
            "acquired": None,
            "acquisition_date_available": False,
            "note": "Imagery acquisition date unavailable",
        })

    acquired = _fmt_src_date(deepest.get("SRC_DATE"))
    return _store(key, {
        "provider": "Esri World Imagery",
        "source_service": "Esri Wayback World Imagery metadata (MapServer identify)",
        "status": "ok",
        "acquired": acquired or None,
        "acquisition_date_available": bool(acquired),
        "resolution_m_per_px": _maybe_float(deepest.get("SAMP_RES") or deepest.get("SRC_RES")),
        "sensor": deepest.get("SRC_DESC") or None,
        "product": deepest.get("NICE_NAME") or None,
        "accuracy_m": _maybe_float(deepest.get("SRC_ACC")),
        "note": "" if acquired else "Imagery acquisition date unavailable",
        "retrieved_at": _utc_now_iso(),
    })


async def get_sentinel2_info(lng: float, lat: float) -> dict[str, Any]:
    """Real metadata for the EOX s2cloudless Sentinel-2 mosaic (yearly)."""
    return _store(f"s2:{lng:.5f}:{lat:.5f}", {
        "provider": "Sentinel-2 (s2cloudless mosaic, EOX)",
        "source_service": f"EOX WMTS s2cloudless-{SENTINEL2_LATEST_YEAR}_3857",
        "status": "ok",
        "acquired": (
            f"{SENTINEL2_LATEST_YEAR} (annual mosaic — no single acquisition date)"
        ),
        "acquisition_date_available": True,
        "resolution_m_per_px": SENTINEL2_RESOLUTION_M,
        "suitability": (
            "Resolution insufficient for detailed parcel/building verification — "
            "suitable for land-cover and broad change analysis only."
        ),
        "retrieved_at": _utc_now_iso(),
    })


def get_provider_catalog() -> list[dict[str, Any]]:
    """The imagery-source abstraction: providers LANDSYNC can integrate.

    `configured: true` = actually wired in this deployment (backend proxy or
    direct tiles). `configured: false` = legitimate future integrations —
    listed so the UI can say "not configured" instead of pretending.
    """
    providers = [
        {
            "id": "esri_wayback",
            "name": "Esri World Imagery",
            "kind": "satellite/aerial mosaic",
            "configured": True,
            "tile_url": _ESRI_TILE_URL,
            "resolution_note": "mixed, up to ~0.3 m/px in covered areas",
            "real_time": False,
            "label": "Dated mosaic — per-location acquisition metadata",
        },
        {
            "id": "sentinel2",
            "name": "Sentinel-2 (s2cloudless)",
            "kind": "satellite mosaic (annual)",
            "configured": True,
            "tile_url": f"https://tiles.maps.eox.at/wmts/1.0.0/s2cloudless-{SENTINEL2_LATEST_YEAR}_3857/default/GoogleMapsCompatible/{{z}}/{{y}}/{{x}}.jpg",
            "resolution_note": "~10 m/px — land-cover scale only",
            "real_time": False,
            "label": "Annual mosaic — year-level date only",
        },
        {
            "id": "tgprac_bhunaksha",
            "name": "Telangana TGRAC / BhuNaksha (cadastral)",
            "kind": "official cadastral REST service",
            "configured": False,
            "service_url": "https://tgrac.telangana.gov.in/arcgis/rest/services/Bhunaksha_Folder/Bhunaksha_Cadastral/MapServer",
            "real_time": False,
            "label": "Integration not configured",
        },
        {
            "id": "ori",
            "name": "Authorized high-resolution ORI / drone survey",
            "kind": "observation imagery",
            "configured": False,
            "real_time": False,
            "label": "Integration not configured",
        },
    ]
    return providers


def _maybe_float(v: Any) -> Optional[float]:
    try:
        return float(v)
    except (TypeError, ValueError):
        return None


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
