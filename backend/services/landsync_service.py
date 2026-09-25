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

import pandas as pd

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

from config import settings
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
_UPLOADS_DIR = _BACKEND_DIR / "uploads"

# Target CRS used by the engine for metric area calculations.
ENGINE_CRS = "EPSG:3857"
# Source CRS of both GeoJSON files (WGS84 / CRS84).
SOURCE_CRS = "EPSG:4326"
# One-shot flag: the degenerate-ML exclusion warning is logged once, not per parcel.
_ML_EXCLUSION_LOGGED = False


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

def _is_upload_path(path: "Path") -> bool:
    """True when the dataset file came from /api/upload (not the built-in sample)."""
    try:
        return _UPLOADS_DIR in path.resolve().parents or path.resolve().parent == _UPLOADS_DIR
    except OSError:
        return False


def _resolve_dataset_paths(dataset_id: str | None) -> tuple[Path, Path]:
    """Resolve the (cadastral, municipal) source pair for a dataset_id.

    Uploads are stored as ``uploads/<dataset_id>_<original_filename>``.

    • No dataset_id (or unknown id) → the built-in sample pair.
    • One uploaded file → treated as the cadastral source, reconciled
      against the built-in sample municipal survey.
    • Two or more uploaded files → first upload (oldest) is the cadastral
      source, the next is the municipal source.
    """
    if not dataset_id or dataset_id == "sample":
        if not settings.DEMO_FIXTURE_MODE:
            logger.error("[landsync_service] Attempted to load sample data while DEMO_FIXTURE_MODE=false")
            raise RuntimeError("REAL_DATA_NOT_AVAILABLE: Synthetic sample data is disabled in production mode.")
        return CADASTRAL_PATH, MUNICIPAL_PATH
    uploads = sorted(
        _UPLOADS_DIR.glob(f"{dataset_id}_*"),
        key=lambda p: p.stat().st_mtime,
    )
    if not uploads:
        if not settings.DEMO_FIXTURE_MODE:
            logger.error("[landsync_service] dataset %r has no uploaded files and DEMO_FIXTURE_MODE=false", dataset_id)
            raise RuntimeError("REAL_DATA_NOT_AVAILABLE: No uploaded datasets found for this ID in production mode.")
        logger.warning(
            "[landsync_service] dataset %r has no uploaded files — using sample data.",
            dataset_id,
        )
        return CADASTRAL_PATH, MUNICIPAL_PATH
    if len(uploads) == 1:
        if not settings.DEMO_FIXTURE_MODE:
            # In production, we must have both sources for reconciliation.
            # If municipal is missing, we cannot fallback to synthetic.
            logger.error("[landsync_service] dataset %r has single upload; municipal source missing and DEMO_FIXTURE_MODE=false", dataset_id)
            raise RuntimeError("REAL_DATA_NOT_AVAILABLE: Municipal source missing. Synthetic fallback disabled in production.")
        logger.info(
            "[landsync_service] dataset %r: single upload %s vs sample municipal survey.",
            dataset_id,
            uploads[0].name,
        )
        return uploads[0], MUNICIPAL_PATH
    logger.info(
        "[landsync_service] dataset %r: %s vs %s.",
        dataset_id,
        uploads[0].name,
        uploads[1].name,
    )
    return uploads[0], uploads[1]


def load_data(
    cadastral_path: "str | Path | None" = None,
    municipal_path: "str | Path | None" = None,
    *,
    force_reload: bool = False,
    dataset_id: str | None = None,
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
    if cadastral_path is None and municipal_path is None:
        cad_path, mun_path = _resolve_dataset_paths(dataset_id)

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
    # Pass the validated (and parcel_id-normalised) frames so the engine
    # never re-reads raw files and bypasses the derived-ID normalisation.
    # The ML predictor (when a validated artifact exists) supplies the ML
    # evidence stream per parcel; absent artifact → MODEL_UNAVAILABLE.
    from services.reconciliation_model import get_predictor

    engine_audit: dict[str, Any] = {}
    engine_results: list[dict] = run_reconciliation(
        cad_path,
        mun_path,
        cadastral_gdf=gdf_cad,
        municipal_gdf=gdf_mun,
        model_predictor=get_predictor(),
        audit=engine_audit,
    )
    logger.info(
        "[landsync_service] Engine returned %d reconciliation records.",
        len(engine_results),
    )

    # ------------------------------------------------------------------
    # 3. Build geometry lookup maps (original EPSG:4326 for frontend)
    #    Key: parcel_id → GeoJSON-serialisable coordinates dict
    #    Memory-bounded: only geometries for parcels the engine actually
    #    matched are converted. Large ward datasets can hold 100k+ features
    #    whose polygons are never served; converting all of them OOM-killed
    #    the container right after a successful reconciliation.
    # ------------------------------------------------------------------
    matched_ids = {rec["parcel_id"] for rec in engine_results}
    cad_geom_map = _build_geometry_map(gdf_cad, only_ids=matched_ids)
    mun_geom_map = _build_geometry_map(gdf_mun, only_ids=matched_ids)

    # Capture CRS strings, then free the raw frames — with 100k+ feature
    # ward files these dominate memory and are no longer needed once the
    # matched-only geometry maps exist.
    cad_crs_str = _crs_string(gdf_cad)
    mun_crs_str = _crs_string(gdf_mun)
    del gdf_cad, gdf_mun
    import gc
    gc.collect()

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
    unmatched_municipal_count = 0
    emitted_ids: set[str] = set()
    for rec in engine_results:
        pid = rec["parcel_id"]

        # ---- UNMATCHED records (spec §6.5): surfaced explicitly ------------
        if rec.get("match_side") == "municipal":
            # A municipal parcel with no cadastral counterpart cannot render
            # in the RECORDED-centric UI; counted in provenance instead of
            # being silently dropped.
            unmatched_municipal_count += 1
            continue
        if rec.get("match_side") == "cadastral":
            cad_geom = cad_geom_map.get(pid)
            if cad_geom is None:
                unmatched_municipal_count += 1
                continue
            parcels.append(
                {
                    "parcel_id": pid,
                    "confidence": 0,
                    "priority": "HIGH",
                    "area_difference": 0.0,
                    "geometry_conflict": False,
                    "attribute_conflict": False,
                    "recommendation": (
                        "No municipal counterpart found for this parcel — "
                        "manual review required."
                    ),
                    "duplicate_id": pid in duplicate_ids,
                    "boundaries": {"cadastral": cad_geom},
                    "match_status": "UNMATCHED",
                    "reconciliation_score": None,
                    "evidence_quality": "INSUFFICIENT",
                    "review_required": True,
                    "review_reasons": [
                        "NO_SPATIAL_MATCH: no municipal parcel overlapped this parcel."
                    ],
                    "model_status": "MODEL_UNAVAILABLE",
                    "nearest_candidate_distance_m": rec.get(
                        "nearest_candidate_distance_m"
                    ),
                    "alternative_candidates": rec.get("alternative_candidates", []),
                }
            )
            emitted_ids.add(pid)
            continue

        if pid in emitted_ids:
            # A parcel ID must map to exactly one record. Later duplicates are
            # dropped so the id→parcel lookup can never be silently overwritten
            # (otherwise two map features would resolve to the same record).
            logger.warning(
                "[landsync_service] Duplicate parcel_id %r in engine output — dropping the later record.",
                pid,
            )
            continue
        emitted_ids.add(pid)

        # `boundaries.cadastral` — always present (source A geometry)
        cad_geom = cad_geom_map.get(pid)
        if cad_geom is None:
            logger.warning(
                "[landsync_service] No cadastral geometry for parcel %r — skipping.",
                pid,
            )
            continue


        # Confidence scoring
        #
        # The engine's rule-based reconciliation is the single source of
        # truth for conflict flags and confidence. The shipped ML pickle is
        # degenerate (trained on a single-class sample: every parcel labeled
        # "conflict", so it predicts a constant for every input). Letting it
        # override or blend into the engine output used to flatten all
        # parcels to the same confidence / conflict values, making different
        # parcels display identical data. ML can be re-enabled here once the
        # model is retrained on genuinely labeled multi-class data.
        # ------------------------------------------------------------------
        final_conflict = rec["geometry_conflict"]
        final_confidence = int(round(rec["confidence"]))
        global _ML_EXCLUSION_LOGGED
        if conflict_detector.classifier is not None and not _ML_EXCLUSION_LOGGED:
            logger.warning(
                "[landsync_service] ML classifier loaded but excluded from scoring: "
                "the model is degenerate (single-class training data). "
                "Engine rule-based confidence is authoritative."
            )
            _ML_EXCLUSION_LOGGED = True

        # `boundaries.drone_ori` — the municipal survey acts as the
        # alternative / drone-survey source. Include it for every parcel that
        # has one so the frontend can always draw both boundaries and the
        # disputed-area overlay; warn when a geometry conflict lacks it.
        mun_geom = mun_geom_map.get(pid)
        boundaries: dict[str, Any] = {"cadastral": cad_geom}
        if mun_geom is not None:
            boundaries["drone_ori"] = mun_geom
        elif rec.get("municipal_geometry") is not None:
            # Spatially-matched parcel: the municipal row's ID differs from
            # the cadastral ID, so the ID-keyed lookup above misses. The
            # pipeline attached the matched municipal geometry directly.
            boundaries["drone_ori"] = rec["municipal_geometry"]
        elif final_conflict:
            logger.warning(
                "[landsync_service] Parcel %r has geometry_conflict=True but no municipal geometry found.",
                pid,
            )

        parcel: dict[str, Any] = {
            # Engine fields (7 mandatory keys)
            "parcel_id": rec["parcel_id"],
            "confidence": int(round(final_confidence)),
            "priority": rec["priority"],
            "area_difference": rec["area_difference"],
            "geometry_conflict": final_conflict,
            "attribute_conflict": rec["attribute_conflict"],
            "recommendation": rec["recommendation"],
            # Derived / frontend-only fields
            "duplicate_id": pid in duplicate_ids,
            "boundaries": boundaries,
        }
        # Structured hybrid-engine evidence (spec §18) — pass through when the
        # engine record carries it; legacy callers ignore the extra keys.
        for _ev_key in (
            "match_status",
            "reconciliation_score",
            "evidence_quality",
            "review_required",
            "review_reasons",
            "model_status",
            "candidate_match_id",
            "spatial_metrics",
            "attribute_metrics",
            "imagery",
            "ml",
        ):
            if _ev_key in rec:
                parcel[_ev_key] = rec[_ev_key]
        parcels.append(parcel)

    # ------------------------------------------------------------------
    # 5. Populate cache
    # ------------------------------------------------------------------
    info: dict[str, Any] = {
        "cadastral_path": str(cad_path),
        "municipal_path": str(mun_path),
        "cadastral_crs": cad_crs_str,
        "municipal_crs": mun_crs_str,
        "cadastral_feature_count": cad_count,
        "municipal_feature_count": mun_count,
        "reconciled_parcel_count": len(parcels),
        "unmatched_municipal_count": unmatched_municipal_count,
        # ---- Data provenance (honest source labelling) ----------------
        # SYNTHETIC_DEMO = built-in synthetic GeoJSON shipped with the repo
        # USER_UPLOADED_REAL = a real file the user uploaded via /api/upload
        # The frontend must NEVER call synthetic data "real".
        "cadastral_source": (
            "USER_UPLOADED_REAL"
            if _is_upload_path(cad_path)
            else "SYNTHETIC_DEMO"
        ),
        "municipal_source": (
            "USER_UPLOADED_REAL"
            if _is_upload_path(mun_path)
            else "SYNTHETIC_DEMO"
        ),
        "reconciliation_type": (
            "REAL_TO_REAL"
            if _is_upload_path(cad_path) and _is_upload_path(mun_path)
            else "MIXED" if _is_upload_path(cad_path) or _is_upload_path(mun_path)
            else "SYNTHETIC_DEMO"
        ),
        "cadastral_filename": Path(cad_path).name,
        "municipal_filename": Path(mun_path).name,
        # ---- Normalisation audit (spec §5): what the engine did to the inputs
        "normalization": engine_audit.get("normalization", {}),
        "duplicate_ids_detected": engine_audit.get("duplicate_ids", {}),
        # ---- Match-status distribution for provenance/reporting (spec §9)
        "match_status_counts": _match_status_counts(parcels),
    }
    _cache.store(parcels, info)
    return info


def _match_status_counts(parcels: list[dict[str, Any]]) -> dict[str, int]:
    """Tally match_status across the result set (honesty metric for §29)."""
    counts: dict[str, int] = {}
    for p in parcels:
        status = p.get("match_status", "UNMATCHED")
        counts[status] = counts.get(status, 0) + 1
    return counts


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

    # Derive a stable parcel_id when the dataset lacks one — real cadastral
    # exports (e.g. GHMC ward shapefiles) carry survey-number columns
    # (OLD_SNO, TS_NO, TSCODE, …) instead of a unified 'parcel_id'.
    if "parcel_id" not in gdf.columns:
        gdf = _derive_parcel_ids(gdf, label)

    return gdf


# Column candidates used to derive a stable parcel identity, in priority
# order. Resolution is PER ROW: the first candidate with a non-empty value
# wins for that row (real ward files have patchy survey columns — e.g.
# OLD_SNO filled for old-town records but empty for newly amalgamated
# plots that only carry TS_NO or TSCODE). Rows where every candidate is
# empty fall back to a deterministic hash of the geometry, so every
# feature still gets a unique, stable ID.
_ID_CANDIDATES: tuple[str, ...] = (
    "parcel_id", "PARCEL_ID",
    "OLD_SNO", "TS_NO1", "TS_NO", "TSCODE", "LGC_NO",
    "survey_no", "SURVEY_NO", "khata_no", "KHATA_NO", "plot_no", "PLOT_NO",
    # CAD-derived ward exports carry the printed survey-number label here:
    "DXF_TEXT",
    "PID", "pid", "ID", "id", "OBJECTID", "FID",
)


def _derive_parcel_ids(gdf: gpd.GeoDataFrame, label: str) -> gpd.GeoDataFrame:
    """Deterministically assign a 'parcel_id' column to *gdf*.

    Strategy (deterministic across restarts — no randomized hash):
    1. Per row, use the first candidate column (in priority order) whose
       value is non-empty — ward files have patchy survey columns, so a
       single dataset-wide column would wrongly degrade most rows to the
       anonymous 'auto-<hash>' identity.
    2. Normalise numeric strings ('123.0' → '123').
    3. Uniquify repeated values with a '-2', '-3' … suffix (real ward files
       often have multiple polygons per survey number).
    4. Rows where every candidate is empty fall back to
       'auto-<md5-of-geometry>' — identical geometries therefore
       intentionally map to the same ID, which the duplicate_id flag
       surfaces.
    """
    import hashlib
    from collections import Counter

    # Normalise every candidate column once (vectorised — cheap at 100k+ rows).
    normalized: list[pd.Series] = []
    for col in _ID_CANDIDATES:
        if col in gdf.columns:
            s = gdf[col].astype(str).str.strip()
            s = s.replace({"": None, "nan": None, "None": None, "0": None})
            s = s.str.replace(r"\.0$", "", regex=True)
            if s.notna().any():
                normalized.append(s)

    if not normalized:
        logger.warning(
            "[landsync_service] %s: no identifier column found — deriving IDs from geometry hashes.",
            label,
        )
        first = pd.Series([None] * len(gdf), index=gdf.index, dtype="object")
        supplier = pd.Series(["geometry"] * len(gdf), index=gdf.index)
    else:
        cand = pd.concat(normalized, axis=1)
        # First non-null value across each row (bfill spreads it to column 0).
        first = cand.bfill(axis=1).iloc[:, 0]
        supplier = cand.notna().idxmax(axis=1).where(first.notna(), other="geometry")
        breakdown = Counter(supplier[supplier != "geometry"])
        summary = ", ".join(f"{cnt} from {col!r}" for col, cnt in breakdown.most_common())
        logger.info(
            "[landsync_service] %s: per-row parcel_id resolution — %s, %d from geometry hashes.",
            label,
            summary or "no column values",
            int((supplier == "geometry").sum()),
        )

    derived: list[str] = []
    seen: dict[str, int] = {}
    for value, geom in zip(first, gdf.geometry):
        if value is None or (isinstance(value, float) and pd.isna(value)):
            try:
                wkt = geom.wkt if geom is not None and not geom.is_empty else ""
            except Exception:
                wkt = ""
            digest = hashlib.md5(wkt.encode("utf-8")).hexdigest()[:8] if wkt else "EMPTY"
            value = f"auto-{digest}"
        count = seen.get(value, 0) + 1
        seen[value] = count
        derived.append(value if count == 1 else f"{value}-{count}")

    gdf = gdf.copy()
    gdf["parcel_id"] = pd.Series(derived, index=gdf.index, dtype="object")
    return gdf


def _build_geometry_map(
    gdf: gpd.GeoDataFrame, only_ids: set[str] | None = None
) -> dict[str, dict]:
    """Build a parcel_id → GeoJSON geometry dict map (EPSG:4326).

    The GeoDataFrame is assumed to already be in EPSG:4326 (CRS84) as loaded
    from the raw GeoJSON file. We do NOT reproject here — the frontend map
    expects WGS84 longitude/latitude coordinates.

    Parameters
    ----------
    gdf : gpd.GeoDataFrame
        Frame whose geometries should be mapped.
    only_ids : set[str], optional
        If given, restrict conversion to these parcel IDs. Large datasets
        (100k+ features) must not have every polygon converted to Python
        dicts — that alone can exhaust container memory.
    """
    import json
    from shapely.geometry import mapping

    # Pre-filter BEFORE iterating: iterrows() materialises a Series per row,
    # which is both slow and wasteful when only a handful of the 100k+ rows
    # are actually needed.
    if only_ids is not None and "parcel_id" in gdf.columns:
        gdf = gdf[gdf["parcel_id"].astype(str).isin(only_ids)]

    geom_map: dict[str, dict] = {}
    for _, row in gdf.iterrows():
        pid = row.get("parcel_id")
        geom = row.geometry
        if pid is None or geom is None or geom.is_empty:
            continue
        # Convert Shapely geometry → GeoJSON-compatible dict
        geom_map[str(pid)] = json.loads(json.dumps(mapping(geom)))
    return geom_map


def _crs_string(gdf: gpd.GeoDataFrame) -> str:
    """Return a human-readable CRS string for the GeoDataFrame."""
    if gdf.crs is None:
        return "unknown"
    epsg = gdf.crs.to_epsg()
    return f"EPSG:{epsg}" if epsg else str(gdf.crs)
