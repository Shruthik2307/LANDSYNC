"""
engine/pipeline.py
==================
End-to-end land-parcel reconciliation pipeline.

Wires together:
    1. engine.crs        — CRS normalisation (→ EPSG:3857, per .agentrules)
    2. engine.geometry   — geometry validation / repair / audit (spec §5)
    3. engine.matching   — parcel pairing (ID join + spatial bbox fallback)
    4. engine.candidates — match-status classification, documented thresholds
    5. engine.metrics    — deterministic GIS evidence (spec §7/§8)
    6. engine.fusion     — evidence fusion → final assessment (spec §14/§19)

Each returned record keeps the full legacy 7-key schema (parcel_id,
confidence, priority, area_difference, geometry_conflict,
attribute_conflict, recommendation) so existing API/tests/UI keep working,
and ADDS the structured evidence fields from spec §18:

    match_status, reconciliation_score, evidence_quality,
    review_required, review_reasons, model_status,
    candidate_match_id, spatial_metrics, attribute_metrics, imagery

Parcels with no municipal counterpart are NOT dropped: they are returned
with match_status UNMATCHED and review_required=True (spec §6.5).
"""

from __future__ import annotations

import json
import logging
import sys
from pathlib import Path
from typing import Any

# ---------------------------------------------------------------------------
# sys.path bootstrap (direct script / module / import all supported)
# ---------------------------------------------------------------------------
_PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(_PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(_PROJECT_ROOT))

import geopandas as gpd
import shapely
import shapely.geometry

from engine.crs import CRSManager
from engine.geometry import normalize_geometries, detect_duplicate_ids
from engine.matching import match_parcels
from engine.conflicts import evaluate_conflicts, _detect_attribute_conflict
from engine.candidates import MatchingThresholds, classify_status
from engine.metrics import compute_pair_metrics
from engine.ml_schema import FEATURE_ORDER, features_from_pair_metrics
from engine.fusion import fuse

logger = logging.getLogger(__name__)

# Module-level default thresholds (documented in MatchingThresholds).
THRESHOLDS = MatchingThresholds()


def run_reconciliation(
    cadastral_path: "str | Path",
    municipal_path: "str | Path",
    *,
    cadastral_gdf: "gpd.GeoDataFrame | None" = None,
    municipal_gdf: "gpd.GeoDataFrame | None" = None,
    thresholds: "MatchingThresholds | None" = None,
    model_predictor: "Any | None" = None,
    audit: "dict | None" = None,
) -> "list[dict[str, Any]]":
    """Load, normalise, match, evaluate, fuse — two parcel GeoJSON datasets.

    Parameters
    ----------
    cadastral_path, municipal_path : str or Path
        GeoJSON paths (used for existence check and audit trail).
    cadastral_gdf, municipal_gdf : geopandas.GeoDataFrame, optional
        Pre-loaded frames to use instead of re-reading from disk.
    thresholds : MatchingThresholds, optional
        Override the documented default classification thresholds.
    model_predictor : callable, optional
        A predictor with ``.predict(feature_vector: list[float]) -> dict``
        returning the ML evidence stream {prediction, probability,
        model_version, model_status} — see
        backend/services/reconciliation_model.py. The predictor performs
        the deterministic OOD check per parcel (spec §16). None → fusion
        reports MODEL_UNAVAILABLE honestly.
    audit : dict, optional
        Caller-provided dict filled with run-level facts (spec §5):
        normalization reports for both sides, CRS, and duplicate-ID maps.

    Returns
    -------
    list[dict]
        Legacy schema + structured evidence per parcel (see module docstring).
    """
    cadastral_path = Path(cadastral_path)
    municipal_path = Path(municipal_path)

    _assert_file_exists(cadastral_path)
    _assert_file_exists(municipal_path)

    th = thresholds or THRESHOLDS

    # ------------------------------------------------------------------
    # Step 1 — Load raw GeoJSON files (or accept pre-validated frames)
    # ------------------------------------------------------------------
    gdf_cadastral = cadastral_gdf if cadastral_gdf is not None else gpd.read_file(cadastral_path)
    gdf_municipal = municipal_gdf if municipal_gdf is not None else gpd.read_file(municipal_path)

    # ------------------------------------------------------------------
    # Step 2 — CRS normalisation (EPSG:3857, metric) — spec §5
    # ------------------------------------------------------------------
    gdf_cadastral = CRSManager.reproject(gdf_cadastral)
    gdf_municipal = CRSManager.reproject(gdf_municipal)

    # ------------------------------------------------------------------
    # Step 2b — Geometry validation / repair / audit — spec §5
    # ------------------------------------------------------------------
    gdf_cadastral, norm_report_cad = normalize_geometries(gdf_cadastral, source_name="cadastral")
    gdf_municipal, norm_report_mun = normalize_geometries(gdf_municipal, source_name="municipal")

    duplicate_ids_cad = detect_duplicate_ids(gdf_cadastral)
    duplicate_ids_mun = detect_duplicate_ids(gdf_municipal)

    if audit is not None:
        audit["normalization"] = {
            "cadastral": norm_report_cad,
            "municipal": norm_report_mun,
            "target_crs": "EPSG:3857",
        }
        audit["duplicate_ids"] = {
            "cadastral": sorted(duplicate_ids_cad.keys()),
            "municipal": sorted(duplicate_ids_mun.keys()),
        }

    # ------------------------------------------------------------------
    # Step 3 — Pair parcels (ID join → spatial bbox fallback) — spec §6
    # ------------------------------------------------------------------
    matched = match_parcels(
        gdf_cadastral,
        gdf_municipal,
        spatial_fallback=True,
    )

    results: list[dict[str, Any]] = []
    transformer = _make_3857_to_4326_transformer()

    def _attrs_from_row(row: Any, side: str) -> dict:
        """Collect non-geometry attributes of one side for agreement checks."""
        out = {}
        for key in row.keys():
            if key.endswith(f"_{side}") and key != f"geometry_{side}":
                field = key[: -len(side) - 1]
                if field in ("parcel_id", "area_m2", "source", "index_right", "index_left"):
                    continue
                val = row[key]
                if val is not None and val == val:  # NaN guard
                    out[field] = val
        return out

    matched_cadastral_ids: set[str] = set()
    municipal_id_by_cadastral: dict[str, str] = {}

    if not matched.empty:
        for _, row in matched.iterrows():
            geom_a = row.get("geometry_a")
            geom_b = row.get("geometry_b")
            pid = str(row.get("parcel_id", "<unknown>"))

            if geom_a is None or geom_b is None or (
                hasattr(geom_a, "is_empty") and geom_a.is_empty
            ) or (
                hasattr(geom_b, "is_empty") and geom_b.is_empty
            ):
                logger.warning(
                    f"[pipeline] WARNING: Parcel {pid!r} has a null/empty geometry — "
                    "returned as REVIEW_REQUIRED with INSUFFICIENT evidence."
                )
                results.append(_insufficient_record(pid))
                matched_cadastral_ids.add(pid)
                continue

            # ---- Legacy conflict evaluation (unchanged behaviour) ----
            record = evaluate_conflicts(row)

            # ---- Deterministic evidence bundle — spec §7/§8 ----
            attrs_a = _attrs_from_row(row, "a")
            attrs_b = _attrs_from_row(row, "b")
            evidence = compute_pair_metrics(geom_a, geom_b, attrs_a, attrs_b)

            # ---- Candidate status — spec §9 ----
            sm = evidence["spatial_metrics"]
            status = classify_status(
                iou=sm["iou"],
                overlap_pct=sm["overlap_pct_of_cadastral"],
                centroid_distance_m=sm["centroid_distance_m"],
                attribute_conflict=record["attribute_conflict"],
                th=th,
            )

            # ---- ML evidence stream (per-parcel OOD check) — spec §10/§16 ----
            ml_stream: dict[str, Any] = {"model_status": "MODEL_UNAVAILABLE"}
            if model_predictor is not None:
                try:
                    feats = features_from_pair_metrics(evidence)
                    if any(v is None for v in feats.values()):
                        # Missing features: do NOT impute silently — skip ML.
                        ml_stream = {
                            "model_status": "MODEL_UNAVAILABLE",
                            "note": "Feature vector incomplete for this parcel.",
                        }
                    else:
                        vector = [float(feats[k]) for k in FEATURE_ORDER]
                        ml_stream = model_predictor.predict(vector)
                except Exception as exc:  # never let ML break determinism
                    logger.warning(
                        f"[pipeline] WARNING: ML predictor failed for {pid!r}: {exc}"
                    )
                    ml_stream = {"model_status": "MODEL_UNAVAILABLE"}

            # ---- Evidence fusion — spec §14/§19 ----
            fused = fuse(
                parcel_id=pid,
                candidate_status=status,
                spatial_metrics=sm,
                attribute_metrics=evidence["attribute_metrics"],
                imagery=evidence["imagery"],
                attribute_conflict=record["attribute_conflict"],
                model=ml_stream,
                duplicate_id=(pid in duplicate_ids_cad or pid in duplicate_ids_mun),
            )

            record.update(
                {
                    "match_status": fused["match_status"],
                    "reconciliation_score": fused["reconciliation_score"],
                    "evidence_quality": fused["evidence_quality"],
                    "review_required": fused["review_required"],
                    "review_reasons": fused["review_reasons"],
                    "model_status": fused["model_status"],
                    "candidate_match_id": row.get("parcel_id_b") or pid,
                    "spatial_metrics": sm,
                    "attribute_metrics": evidence["attribute_metrics"],
                    "imagery": evidence["imagery"],
                    "ml": fused["ml"],
                }
            )

            # Attach the municipal geometry (EPSG:4326 GeoJSON) for the
            # frontend drone_ori overlay — same as the legacy behaviour.
            try:
                geom_b_4326 = shapely.ops.transform(
                    lambda x, y: transformer.transform(x, y), row["geometry_b"]
                )
                record["municipal_geometry"] = json.loads(
                    json.dumps(shapely.geometry.mapping(geom_b_4326))
                )
            except Exception as exc:  # geometry transport is best-effort
                logger.warning(
                    f"[pipeline] WARNING: Could not attach municipal geometry for "
                    f"parcel {pid!r}: {exc}"
                )

            results.append(record)
            matched_cadastral_ids.add(pid)
            municipal_id_by_cadastral[pid] = str(row.get("parcel_id_b") or pid)

    # ------------------------------------------------------------------
    # Step 4 — UNMATCHED cadastral parcels (spec §6.5): never silent
    # ------------------------------------------------------------------
    unmatched = [
        pid for pid in gdf_cadastral["parcel_id"].tolist()
        if str(pid) not in matched_cadastral_ids
    ]
    if unmatched and not gdf_municipal.empty:
        from engine.candidates import find_candidates, rank_candidates, build_unmatched_record

        b_geometry_by_id = dict(
            zip(gdf_municipal["parcel_id"].tolist(), gdf_municipal.geometry)
        )
        unmatched_gdf = gdf_cadastral[gdf_cadastral["parcel_id"].astype(str).isin(unmatched)]
        candidate_map = find_candidates(
            unmatched_gdf, gdf_municipal, th=th, id_col="parcel_id"
        )
        for pid in unmatched:
            cands = candidate_map.get(str(pid), [])
            best_dist = cands[0]["centroid_distance_m"] if cands else None
            rec = build_unmatched_record(pid, "cadastral", best_dist)
            # Rank candidates for review context (bounded work per parcel).
            geom_a = gdf_cadastral.loc[
                gdf_cadastral["parcel_id"].astype(str) == str(pid), "geometry"
            ]
            if not geom_a.empty and cands:
                ranked = rank_candidates(
                    geom_a.iloc[0], cands, b_geometry_by_id, th=th
                )
                rec["alternative_candidates"] = [
                    {
                        "municipal_id": c.municipal_id,
                        "iou": c.iou,
                        "overlap_pct": c.overlap_pct,
                        "centroid_distance_m": c.centroid_distance_m,
                        "status": c.status,
                    }
                    for c in ranked[: th.max_candidates]
                ]
            results.append(rec)

    # ------------------------------------------------------------------
    # Step 5 — UNMATCHED municipal parcels (reported, not reconciled)
    # ------------------------------------------------------------------
    matched_municipal_ids = set(municipal_id_by_cadastral.values())
    for mid in gdf_municipal["parcel_id"].tolist():
        if str(mid) not in matched_municipal_ids:
            results.append(build_unmatched_record(mid, "municipal", None))

    return results


def _insufficient_record(pid: str) -> dict:
    """Legacy-shaped record for parcels whose geometry cannot be measured."""
    return {
        "parcel_id": pid,
        "confidence": 0,
        "priority": "HIGH",
        "area_difference": 0.0,
        "geometry_conflict": True,
        "attribute_conflict": False,
        "recommendation": "Geometry missing or empty — manual review required.",
        "match_status": "REVIEW_REQUIRED",
        "reconciliation_score": None,
        "evidence_quality": "INSUFFICIENT",
        "review_required": True,
        "review_reasons": ["INVALID_GEOMETRY: null or empty boundary geometry."],
        "model_status": "MODEL_UNAVAILABLE",
        "candidate_match_id": None,
        "spatial_metrics": {},
        "attribute_metrics": {},
        "imagery": {"available": False},
        "ml": {"model_status": "MODEL_UNAVAILABLE"},
    }


def _make_3857_to_4326_transformer():
    """Return a cached pyproj transformer EPSG:3857 → EPSG:4326."""
    from functools import lru_cache
    from pyproj import Transformer

    @lru_cache(maxsize=1)
    def _build():
        return Transformer.from_crs(3857, 4326, always_xy=True)

    return _build()


# ---------------------------------------------------------------------------
# Private helpers
# ---------------------------------------------------------------------------

def _assert_file_exists(path: Path) -> None:
    """Raise FileNotFoundError with a clear message if *path* is absent."""
    if not path.exists():
        raise FileNotFoundError(
            f"Input file not found: {path.resolve()}\n"
            "Ensure both GeoJSON paths are correct before running the pipeline."
        )


# ---------------------------------------------------------------------------
# CLI entry point
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(message)s")
    if len(sys.argv) == 3:
        _cadastral = sys.argv[1]
        _municipal = sys.argv[2]
    else:
        _project_root = Path(__file__).resolve().parent.parent
        _cadastral = _project_root / "data" / "sample" / "cadastral.geojson"
        _municipal = _project_root / "data" / "sample" / "municipal.geojson"

    logger.info(f"[pipeline] Cadastral : {_cadastral}")
    logger.info(f"[pipeline] Municipal : {_municipal}")
    logger.info("")

    _results = run_reconciliation(_cadastral, _municipal)

    logger.info(f"[pipeline] {len(_results)} reconciliation record(s) produced.\n")
    logger.info(json.dumps(_results, indent=2))
