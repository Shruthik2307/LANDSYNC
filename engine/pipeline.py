"""
engine/pipeline.py
==================
End-to-end land-parcel reconciliation pipeline.

Wires together:
    1. engine.crs       — CRS normalisation (-> EPSG:3857, as mandated by .agentrules)
    2. engine.matching  — Parcel pairing (ID join + spatial bounding-box fallback)
    3. engine.conflicts — Conflict evaluation & confidence scoring

Public API
----------
run_reconciliation(cadastral_path, municipal_path) -> list[dict]
    Load two GeoJSON files, pair their parcels, evaluate conflicts, and
    return a list of record dicts that strictly conform to the schema in
    .agentrules:

        {
            'parcel_id':         str,
            'confidence':        int,        # 0-100
            'priority':          str,        # 'HIGH' | 'MEDIUM' | 'LOW'
            'area_difference':   float,      # signed m2  (area_a - area_b)
            'geometry_conflict': bool,
            'attribute_conflict': bool,
            'recommendation':    str,
        }

Usage
-----
>>> from engine.pipeline import run_reconciliation
>>> results = run_reconciliation("data/sample/cadastral.geojson",
...                              "data/sample/municipal.geojson")
>>> for r in results:
...     print(r)
"""

from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any

# ---------------------------------------------------------------------------
# sys.path bootstrap — ensures `engine` is importable whether the script is
# invoked as:
#   python engine/pipeline.py          (direct script)
#   python -m engine.pipeline          (module)
#   from engine.pipeline import ...    (import)
# ---------------------------------------------------------------------------
_PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(_PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(_PROJECT_ROOT))

import geopandas as gpd
import shapely

from engine.crs import CRSManager
from engine.matching import match_parcels
from engine.conflicts import evaluate_conflicts


# ---------------------------------------------------------------------------
# Public entry point
# ---------------------------------------------------------------------------

def run_reconciliation(
    cadastral_path: "str | Path",
    municipal_path: "str | Path",
    *,
    cadastral_gdf: "gpd.GeoDataFrame | None" = None,
    municipal_gdf: "gpd.GeoDataFrame | None" = None,
) -> "list[dict[str, Any]]":
    """Load, normalise, match, and evaluate two parcel GeoJSON datasets.

    Parameters
    ----------
    cadastral_path : str or Path
        Path to the cadastral GeoJSON file.
    municipal_path : str or Path
        Path to the municipal GeoJSON file.
    cadastral_gdf, municipal_gdf : geopandas.GeoDataFrame, optional
        Pre-loaded frames to use instead of re-reading *path* from disk.
        The service layer passes these so that validation-time
        normalisation (e.g. derived ``parcel_id`` columns for real
        cadastral exports) is not silently bypassed when the engine
        re-reads the raw files.

    Returns
    -------
    list[dict]
        One dict per matched parcel pair, strictly adhering to the output
        schema defined in .agentrules.  Records with missing or null
        geometries are skipped with a warning printed to stderr.

    Raises
    ------
    FileNotFoundError
        If either input path does not exist.
    ValueError
        If a GeoDataFrame has no CRS defined (propagated from CRSManager).
    """
    cadastral_path = Path(cadastral_path)
    municipal_path = Path(municipal_path)

    _assert_file_exists(cadastral_path)
    _assert_file_exists(municipal_path)

    # ------------------------------------------------------------------
    # Step 1 -- Load raw GeoJSON files (or accept pre-validated frames)
    # ------------------------------------------------------------------
    gdf_cadastral = cadastral_gdf if cadastral_gdf is not None else gpd.read_file(cadastral_path)
    gdf_municipal = municipal_gdf if municipal_gdf is not None else gpd.read_file(municipal_path)

    # ------------------------------------------------------------------
    # Step 2 -- Normalise CRS to EPSG:3857 (rule: .agentrules section CRS)
    # ------------------------------------------------------------------
    gdf_cadastral = CRSManager.reproject(gdf_cadastral)
    gdf_municipal = CRSManager.reproject(gdf_municipal)

    # ------------------------------------------------------------------
    # Step 3 -- Pair parcels (ID join -> spatial bounding-box fallback)
    # ------------------------------------------------------------------
    matched = match_parcels(
        gdf_cadastral,
        gdf_municipal,
        spatial_fallback=True,
    )

    if matched.empty:
        print(
            "[pipeline] WARNING: No parcel matches found between the two datasets.",
            file=sys.stderr,
        )
        return []

    # ------------------------------------------------------------------
    # Step 4 -- Evaluate conflicts row-by-row and collect results
    # ------------------------------------------------------------------
    results = []

    for _, row in matched.iterrows():
        geom_a = row.get("geometry_a")
        geom_b = row.get("geometry_b")

        if geom_a is None or geom_b is None:
            pid = row.get("parcel_id", "<unknown>")
            print(
                f"[pipeline] WARNING: Parcel {pid!r} has a null geometry -- "
                "skipping conflict evaluation.",
                file=sys.stderr,
            )
            continue

        if hasattr(geom_a, "is_empty") and geom_a.is_empty:
            pid = row.get("parcel_id", "<unknown>")
            print(
                f"[pipeline] WARNING: Parcel {pid!r} geometry_a is empty -- "
                "skipping.",
                file=sys.stderr,
            )
            continue

        if hasattr(geom_b, "is_empty") and geom_b.is_empty:
            pid = row.get("parcel_id", "<unknown>")
            print(
                f"[pipeline] WARNING: Parcel {pid!r} geometry_b is empty -- "
                "skipping.",
                file=sys.stderr,
            )
            continue

        record = evaluate_conflicts(row)

        # Attach the municipal geometry (converted back to EPSG:4326 GeoJSON)
        # so the service layer can always provide the drone_ori overlay —
        # including spatially-matched parcels whose municipal ID differs from
        # the cadastral ID, where an ID-keyed lookup cannot find it.
        try:
            transformer = _make_3857_to_4326_transformer()
            geom_b_4326 = shapely.ops.transform(
                lambda x, y: transformer.transform(x, y), row["geometry_b"]
            )
            record["municipal_geometry"] = json.loads(
                json.dumps(shapely.geometry.mapping(geom_b_4326))
            )
        except Exception as exc:  # geometry transport is best-effort
            print(
                f"[pipeline] WARNING: Could not attach municipal geometry for "
                f"parcel {row.get('parcel_id')!r}: {exc}",
                file=sys.stderr,
            )

        results.append(record)

    return results# ---------------------------------------------------------------------------
# Private helpers

def _make_3857_to_4326_transformer():
    """Return a cached pyproj transformer EPSG:3857 → EPSG:4326."""
    from functools import lru_cache
    from pyproj import Transformer

    @lru_cache(maxsize=1)
    def _build():
        return Transformer.from_crs(3857, 4326, always_xy=True)

    return _build()


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
    if len(sys.argv) == 3:
        _cadastral = sys.argv[1]
        _municipal = sys.argv[2]
    else:
        _project_root = Path(__file__).resolve().parent.parent
        _cadastral = _project_root / "data" / "sample" / "cadastral.geojson"
        _municipal = _project_root / "data" / "sample" / "municipal.geojson"

    print(f"[pipeline] Cadastral : {_cadastral}")
    print(f"[pipeline] Municipal : {_municipal}")
    print()

    _results = run_reconciliation(_cadastral, _municipal)

    print(f"[pipeline] {len(_results)} reconciliation record(s) produced.\n")
    print(json.dumps(_results, indent=2))
