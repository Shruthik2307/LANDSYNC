"""
backend/services/landsync_service.py
=====================================
Core service layer that bridges FastAPI routes to the LANDSYNC engine.

Responsibilities
----------------
1. Load cadastral + municipal GeoJSON from disk using GeoPandas.
2. Validate geometries and CRS before passing to the engine.
3. Call engine.pipeline.run_reconciliation() to get scored parcel records.
4. Map engine output → frontend Parcel schema (adds `boundaries`, `duplicate_id`).
5. Cache results in-memory so repeated API calls are cheap (no redundant GIS work).
6. Expose get_all_parcels(), get_parcel_by_id(), get_conflicts(), get_dataset_info().

CRS note
--------
The engine (engine.crs.CRSManager) reprojects all data to EPSG:3857 internally
for metric area calculations. The `boundaries` field returned to the frontend
uses the original EPSG:4326 coordinates (as loaded from the GeoJSON files) so
that the map renders correctly.

Single-source mode
------------------
Phase 1 has both cadastral.geojson and municipal.geojson with matching parcel IDs.
The engine runs full two-source reconciliation. If a second source is not available
in a future upload scenario, the service raises DataNotReadyError.
"""

from __future__ import annotations

import logging
import sys
from pathlib import Path
from typing import Any

# ---------------------------------------------------------------------------
# sys.path bootstrap — ensure the project root is on sys.path so that
# `import engine` resolves whether this module is imported from:
#   • backend/    (uvicorn main:app)
#   • project root  (pytest)
# ---------------------------------------------------------------------------
_BACKEND_DIR = Path(__file__).resolve().parent.parent   # backend/
_PROJECT_ROOT = _BACKEND_DIR.parent                     # LANDSYNC/
for _p in (_PROJECT_ROOT, _BACKEND_DIR):
    if str(_p) not in sys.path:
        sys.path.insert(0, str(_p))

import geopandas as gpd

from engine.pipeline import run_reconciliation
from services.ml_service import conflict_detector, topology_validator

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Well-known data paths
# ---------------------------------------------------------------------------
_DATA_DIR = _PROJECT_ROOT / "data" / "sample"
CADASTRAL_PATH = _DATA_DIR / "cadastral.geojson"
MUNICIPAL_PATH = _DATA_DIR / "municipal.geojson"

# Target CRS used by the engine for metric area calculations.
ENGINE_CRS = "EPSG:3857"
# Source CRS of both GeoJSON files (WGS84 / CRS84).
SOURCE_CRS = "EPSG:4326"


# ---------------------------------------------------------------------------
# Custom exceptions
# ---------------------------------------------------------------------------

class DataNotReadyError(RuntimeError):
    """Raised when the service has not been loaded yet."""


class ParcelNotFoundError(KeyError):
    """Raised when a parcel_id does not exist in the result set."""


# ---------------------------------------------------------------------------
# In-memory cache
# ---------------------------------------------------------------------------

class _Cache:
    """Simple container for the computed reconciliation results."""

    def __init__(self) -> None:
        self._parcels: list[dict[str, Any]] = []
        self._by_id: dict[str, dict[str, Any]] = {}
        self._loaded: bool = False
        self._info: dict[str, Any] = {}

    @property
    def loaded(self) -> bool:
        return self._loaded

    def store(
        self,
        parcels: list[dict[str, Any]],
        info: dict[str, Any],
    ) -> None:
        self._parcels = parcels
        self._by_id = {p["parcel_id"]: p for p in parcels}
        self._info = info
        self._loaded = True
        logger.info(
            "[landsync_service] Cache populated: %d parcels stored.", len(parcels)
        )

    def all_parcels(self) -> list[dict[str, Any]]:
        if not self._loaded:
            raise DataNotReadyError(
                "Parcel data has not been loaded. Call load_data() first."
            )
        return list(self._parcels)

    def by_id(self, parcel_id: str) -> dict[str, Any]:
        if not self._loaded:
            raise DataNotReadyError(
                "Parcel data has not been loaded. Call load_data() first."
            )
        try:
            return dict(self._by_id[parcel_id])
        except KeyError:
            raise ParcelNotFoundError(parcel_id)

    def info(self) -> dict[str, Any]:
        return dict(self._info)

    def clear(self) -> None:
        self._parcels = []
        self._by_id = {}
        self._loaded = False
        self._info = {}


_cache = _Cache()


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def load_data(
    cadastral_path: "str | Path | None" = None,
    municipal_path: "str | Path | None" = None,
    *,
    force_reload: bool = False,
) -> dict[str, Any]:
    """Load and reconcile cadastral + municipal GeoJSON, populate cache.

    Parameters
    ----------
    cadastral_path : str or Path, optional
        Path to the cadastral GeoJSON. Defaults to data/sample/cadastral.geojson.
    municipal_path : str or Path, optional
        Path to the municipal GeoJSON. Defaults to data/sample/municipal.geojson.
    force_reload : bool
        If True, discard any existing cache and reload from disk.

    Returns
    -------
    dict
        Dataset information summary (CRS, feature counts, file paths).

    Raises
    ------
    FileNotFoundError
        If either GeoJSON file is absent.
    ValueError
        If either GeoDataFrame has invalid / missing CRS.
    RuntimeError
        If the engine returns zero reconciliation records.
    """
    if _cache.loaded and not force_reload:
        logger.debug("[landsync_service] Cache hit — skipping reload.")
        return _cache.info()

    cad_path = Path(cadastral_path) if cadastral_path else CADASTRAL_PATH
    mun_path = Path(municipal_path) if municipal_path else MUNICIPAL_PATH

    _assert_file_exists(cad_path, "cadastral")
    _assert_file_exists(mun_path, "municipal")

    logger.info("[landsync_service] Loading cadastral: %s", cad_path)
    logger.info("[landsync_service] Loading municipal : %s", mun_path)

    # ------------------------------------------------------------------
    # 1. Load raw GeoDataFrames (EPSG:4326 / CRS84)
    # ------------------------------------------------------------------
    gdf_cad = _load_and_validate(cad_path, "cadastral")
    gdf_mun = _load_and_validate(mun_path, "municipal")

    cad_count = len(gdf_cad)
    mun_count = len(gdf_mun)
    logger.info(
        "[landsync_service] Loaded %d cadastral, %d municipal features.",
        cad_count,
        mun_count,
    )

    # ------------------------------------------------------------------
    # 2. Run engine reconciliation (handles CRS reprojection internally)
    # ------------------------------------------------------------------
    logger.info("[landsync_service] Running engine reconciliation …")
    engine_results: list[dict] = run_reconciliation(cad_path, mun_path)
    logger.info(
        "[landsync_service] Engine returned %d reconciliation records.",
        len(engine_results),
    )

    # ------------------------------------------------------------------
    # 3. Build geometry lookup maps (original EPSG:4326 for frontend)
    #    Key: parcel_id → GeoJSON-serialisable coordinates dict
    # ------------------------------------------------------------------
    cad_geom_map = _build_geometry_map(gdf_cad)
    mun_geom_map = _build_geometry_map(gdf_mun)

    # ------------------------------------------------------------------
    # 4. Map engine output → frontend Parcel schema
    # ------------------------------------------------------------------
    # Detect duplicate parcel IDs across the result set.
    seen_ids: dict[str, int] = {}
    for rec in engine_results:
        pid = rec["parcel_id"]
        seen_ids[pid] = seen_ids.get(pid, 0) + 1
    duplicate_ids = {pid for pid, cnt in seen_ids.items() if cnt > 1}

    parcels: list[dict[str, Any]] = []
    for rec in engine_results:
        pid = rec["parcel_id"]

        # `boundaries.cadastral` — always present (source A geometry)
        cad_geom = cad_geom_map.get(pid)
        if cad_geom is None:
            logger.warning(
                "[landsync_service] No cadastral geometry for parcel %r — skipping.",
                pid,
            )
            continue

        # `boundaries.drone_ori` — present only when geometry_conflict == True
        # (the municipal survey acts as the alternative / drone-survey source)
        mun_geom = mun_geom_map.get(pid)
        boundaries: dict[str, Any] = {"cadastral": cad_geom}
        if rec["geometry_conflict"] and mun_geom is not None:
            boundaries["drone_ori"] = mun_geom

        # ------------------------------------------------------------------
        # ML-powered conflict detection and confidence scoring
        # ------------------------------------------------------------------
        try:
            has_ml_conflict, ml_confidence = conflict_detector.predict_conflict(rec)
            # Use ML confidence if model trained, otherwise use engine confidence
            final_confidence = ml_confidence if conflict_detector.classifier else rec["confidence"]
            final_conflict = has_ml_conflict if conflict_detector.classifier else rec["geometry_conflict"]
        except Exception as e:
            logger.warning(f"ML prediction failed for {pid}: {e}, using engine values")
            final_confidence = rec["confidence"]
            final_conflict = rec["geometry_conflict"]

        parcel: dict[str, Any] = {
            # Engine fields (7 mandatory keys)
            "parcel_id": rec["parcel_id"],
            "confidence": final_confidence,
            "priority": rec["priority"],
            "area_difference": rec["area_difference"],
            "geometry_conflict": final_conflict,
            "attribute_conflict": rec["attribute_conflict"],
            "recommendation": rec["recommendation"],
            # Derived / frontend-only fields
            "duplicate_id": pid in duplicate_ids,
            "boundaries": boundaries,
        }
        parcels.append(parcel)

    # ------------------------------------------------------------------
    # 5. Populate cache
    # ------------------------------------------------------------------
    info: dict[str, Any] = {
        "cadastral_path": str(cad_path),
        "municipal_path": str(mun_path),
        "cadastral_crs": _crs_string(gdf_cad),
        "municipal_crs": _crs_string(gdf_mun),
        "engine_crs": ENGINE_CRS,
        "cadastral_feature_count": cad_count,
        "municipal_feature_count": mun_count,
        "reconciled_parcel_count": len(parcels),
    }
    _cache.store(parcels, info)
    return info


def get_all_parcels() -> list[dict[str, Any]]:
    """Return all reconciled parcels.

    Raises
    ------
    DataNotReadyError
        If load_data() has not been called.
    """
    return _cache.all_parcels()


def get_parcel_by_id(parcel_id: str) -> dict[str, Any]:
    """Return a single parcel by ID.

    Raises
    ------
    DataNotReadyError
        If load_data() has not been called.
    ParcelNotFoundError
        If the parcel_id does not exist.
    """
    return _cache.by_id(parcel_id)


def get_conflicts() -> list[dict[str, Any]]:
    """Return conflict parcels sorted by priority (HIGH first) then confidence (desc).

    A parcel is a conflict if geometry_conflict OR attribute_conflict OR duplicate_id.

    Raises
    ------
    DataNotReadyError
        If load_data() has not been called.
    """
    priority_order = {"HIGH": 0, "MEDIUM": 1, "LOW": 2}
    all_parcels = _cache.all_parcels()
    conflicts = [
        p for p in all_parcels
        if p["geometry_conflict"] or p["attribute_conflict"] or p["duplicate_id"]
    ]
    conflicts.sort(
        key=lambda p: (priority_order.get(p["priority"], 3), -p["confidence"])
    )
    return conflicts


def get_dataset_info() -> dict[str, Any]:
    """Return metadata about the currently loaded dataset."""
    return _cache.info()


def is_loaded() -> bool:
    """Return True if data has been loaded and the cache is populated."""
    return _cache.loaded


def reload(
    cadastral_path: "str | Path | None" = None,
    municipal_path: "str | Path | None" = None,
) -> dict[str, Any]:
    """Force a full reload from disk (clears the in-memory cache first).

    Useful after a new file is uploaded via /api/upload.
    """
    _cache.clear()
    return load_data(
        cadastral_path=cadastral_path,
        municipal_path=municipal_path,
        force_reload=True,
    )


# ---------------------------------------------------------------------------
# Private helpers
# ---------------------------------------------------------------------------

def _assert_file_exists(path: Path, label: str) -> None:
    """Raise FileNotFoundError with a descriptive message if path is absent."""
    if not path.exists():
        raise FileNotFoundError(
            f"[landsync_service] {label} file not found: {path.resolve()}\n"
            "Ensure the sample data directory contains both GeoJSON files."
        )


def _load_and_validate(path: Path, label: str) -> gpd.GeoDataFrame:
    """Read a GeoJSON file and validate it minimally.

    Raises
    ------
    ValueError
        If the GeoDataFrame is empty, has no CRS, or has no geometry column.
    """
    try:
        gdf = gpd.read_file(path)
    except Exception as exc:
        raise ValueError(
            f"[landsync_service] Failed to parse {label} GeoJSON ({path}): {exc}"
        ) from exc

    if gdf.empty:
        raise ValueError(
            f"[landsync_service] {label} GeoDataFrame is empty ({path})."
        )

    if gdf.crs is None:
        # Try setting EPSG:4326 if unspecified (common for CRS84 files without
        # an explicit authority-encoded CRS string that pyproj can parse).
        logger.warning(
            "[landsync_service] %s has no CRS — assuming EPSG:4326.", label
        )
        gdf = gdf.set_crs(epsg=4326)

    # Validate geometry column
    if gdf.geometry is None or gdf.geometry.name not in gdf.columns:
        raise ValueError(
            f"[landsync_service] {label} GeoDataFrame has no geometry column."
        )

    # Warn about null / invalid geometries (don't drop them — engine handles this)
    null_geoms = gdf.geometry.isna().sum()
    invalid_geoms = (~gdf.geometry.is_valid).sum()
    if null_geoms:
        logger.warning(
            "[landsync_service] %s: %d null geometries detected.", label, null_geoms
        )
    if invalid_geoms:
        logger.warning(
            "[landsync_service] %s: %d invalid geometries detected.", label, invalid_geoms
        )

    # Validate required column
    if "parcel_id" not in gdf.columns:
        raise ValueError(
            f"[landsync_service] {label} GeoDataFrame is missing required column "
            f"'parcel_id'. Available columns: {list(gdf.columns)}"
        )

    return gdf


def _build_geometry_map(gdf: gpd.GeoDataFrame) -> dict[str, dict]:
    """Build a parcel_id → GeoJSON geometry dict map (EPSG:4326).

    The GeoDataFrame is assumed to already be in EPSG:4326 (CRS84) as loaded
    from the raw GeoJSON file. We do NOT reproject here — the frontend map
    expects WGS84 longitude/latitude coordinates.
    """
    geom_map: dict[str, dict] = {}
    for _, row in gdf.iterrows():
        pid = row.get("parcel_id")
        geom = row.geometry
        if pid is None or geom is None or geom.is_empty:
            continue
        # Convert Shapely geometry → GeoJSON-compatible dict
        import json
        from shapely.geometry import mapping
        geom_map[str(pid)] = json.loads(json.dumps(mapping(geom)))
    return geom_map


def _crs_string(gdf: gpd.GeoDataFrame) -> str:
    """Return a human-readable CRS string for the GeoDataFrame."""
    if gdf.crs is None:
        return "unknown"
    epsg = gdf.crs.to_epsg()
    return f"EPSG:{epsg}" if epsg else str(gdf.crs)
