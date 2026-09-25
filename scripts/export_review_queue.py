"""
scripts/export_review_queue.py
==============================
Export the parcel comparisons from the currently loaded dataset to a CSV
for offline human review (spec §4). Each row carries the full deterministic
evidence so a reviewer can label without re-running the engine.

The engine's own match_status is exported as *evidence context* — the
reviewer makes the final call; nothing is auto-labeled (spec §4/§21).

Usage:
    python scripts/export_review_queue.py [output.csv]

Default output: data/verified/review_queue.csv
Requires a loaded engine cache (run the backend, or load_data() first).
"""

from __future__ import annotations

import csv
import json
import sys
from pathlib import Path

_PROJECT_ROOT = Path(__file__).resolve().parent.parent
for _p in (_PROJECT_ROOT, _PROJECT_ROOT / "backend"):
    if str(_p) not in sys.path:
        sys.path.insert(0, str(_p))

DEFAULT_OUT = _PROJECT_ROOT / "data" / "verified" / "review_queue.csv"

COLUMNS = [
    "cadastral_id",
    "municipal_id",
    "region",
    "engine_match_status",
    "reconciliation_score",
    "iou",
    "area_ratio",
    "area_difference_m2",
    "centroid_distance_m",
    "hausdorff_distance_m",
    "boundary_displacement_m",
    "shape_similarity",
    "overlap_pct_of_cadastral",
    "perimeter_difference_m",
    "survey_number_match",
    "land_use_match",
    "classification_match",
    "imagery_available",
    "imagery_acquisition_date",
    "boundaries_geojson",
    "label_to_fill",
    "reviewer_to_fill",
    "notes_to_fill",
]


def main() -> int:
    out_path = Path(sys.argv[1]) if len(sys.argv) > 1 else DEFAULT_OUT

    from services.landsync_service import _cache, is_loaded

    if not is_loaded():
        print(
            "REAL_DATA_NOT_AVAILABLE: the engine cache is empty. "
            "Start the backend and load a real dataset (upload + process) "
            "before exporting a review queue."
        )
        return 2

    info = _cache.info()
    region = (
        f"upload:{info.get('cadastral_filename')}"
        if info.get("cadastral_source") == "upload"
        else f"sample:{info.get('cadastral_filename')}"
    )
    if info.get("cadastral_source") != "upload":
        print(
            "WARNING: the loaded dataset is the bundled SYNTHETIC sample. "
            "Labels derived from it can never be used for production training "
            "(the label store will reject them). Export is allowed for "
            "workflow rehearsal only."
        )

    rows = []
    for p in _cache.all_parcels():
        boundaries = p.get("boundaries", {})
        if not boundaries.get("cadastral"):
            continue
        sm = p.get("spatial_metrics", {}) or {}
        am = p.get("attribute_metrics", {}) or {}
        im = p.get("imagery", {}) or {}
        rows.append(
            {
                "cadastral_id": p["parcel_id"],
                "municipal_id": p.get("candidate_match_id") or p["parcel_id"],
                "region": region,
                "engine_match_status": p.get("match_status"),
                "reconciliation_score": p.get("reconciliation_score"),
                "iou": sm.get("iou"),
                "area_ratio": sm.get("area_ratio"),
                "area_difference_m2": sm.get("area_difference_m2"),
                "centroid_distance_m": sm.get("centroid_distance_m"),
                "hausdorff_distance_m": sm.get("hausdorff_distance_m"),
                "boundary_displacement_m": sm.get("boundary_displacement_m"),
                "shape_similarity": sm.get("shape_similarity"),
                "overlap_pct_of_cadastral": sm.get("overlap_pct_of_cadastral"),
                "perimeter_difference_m": sm.get("perimeter_difference_m"),
                "survey_number_match": am.get("survey_number_match"),
                "land_use_match": am.get("land_use_match"),
                "classification_match": am.get("classification_match"),
                "imagery_available": im.get("available", False),
                "imagery_acquisition_date": im.get("acquisition_date"),
                "boundaries_geojson": json.dumps(boundaries, ensure_ascii=False),
                "label_to_fill": "",
                "reviewer_to_fill": "",
                "notes_to_fill": "",
            }
        )

    out_path.parent.mkdir(parents=True, exist_ok=True)
    with open(out_path, "w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=COLUMNS)
        writer.writeheader()
        writer.writerows(rows)

    print(f"Exported {len(rows)} comparison rows → {out_path}")
    print(
        "A human reviewer fills label_to_fill "
        "(MATCH|MINOR_DISCREPANCY|MAJOR_DISCREPANCY|UNMATCHED|REVIEW) and "
        "reviewer_to_fill, then imports via scripts/import_verified_labels.py."
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
