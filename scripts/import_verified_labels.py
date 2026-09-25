"""
scripts/import_verified_labels.py
=================================
Import reviewer-completed CSV rows into the validated label store
(data/verified/labels.jsonl), reusing backend/services/label_store validation so
CSV imports are held to exactly the same honesty rules as the API
(schema, dedupe, synthetic-provenance rejection).

Rows with empty label_to_fill or reviewer_to_fill are skipped and
reported. Rows failing validation are reported and NOT written —
nothing silently passes.

Usage:
    python scripts/import_verified_labels.py <completed_review.csv>
"""

from __future__ import annotations

import csv
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

_PROJECT_ROOT = Path(__file__).resolve().parent.parent
for _p in (_PROJECT_ROOT, _PROJECT_ROOT / "backend"):
    if str(_p) not in sys.path:
        sys.path.insert(0, str(_p))

from backend.services.label_store import LabelStoreError, append_label, load_labels  # noqa: E402

VALID_IMPORT_LABELS = (
    "MATCH",
    "MINOR_DISCREPANCY",
    "MAJOR_DISCREPANCY",
    "UNMATCHED",
    "REVIEW",
)


def main() -> int:
    if len(sys.argv) != 2:
        print(__doc__)
        return 2
    csv_path = Path(sys.argv[1])
    if not csv_path.exists():
        print(f"ERROR: review CSV not found: {csv_path}")
        return 2

    with open(csv_path, "r", encoding="utf-8-sig", newline="") as f:
        rows = list(csv.DictReader(f))

    imported, skipped_empty, rejected = 0, 0, []
    for line_no, row in enumerate(rows, start=2):  # header is line 1
        label = (row.get("label_to_fill") or "").strip().upper()
        reviewer = (row.get("reviewer_to_fill") or "").strip()
        if not label and not reviewer:
            continue  # untouched row
        if not label or not reviewer:
            rejected.append((line_no, "label or reviewer missing — row incomplete"))
            continue
        if label not in VALID_IMPORT_LABELS:
            rejected.append((line_no, f"invalid label {label!r}"))
            continue

        # Rebuild the pair_metrics object from the flat CSV columns so the
        # stored record carries the full reproducible evidence.
        sm = {
            "iou": _float(row.get("iou")),
            "area_ratio": _float(row.get("area_ratio")),
            "area_difference_m2": _float(row.get("area_difference_m2")),
            "centroid_distance_m": _float(row.get("centroid_distance_m")),
            "hausdorff_distance_m": _float(row.get("hausdorff_distance_m")),
            "boundary_displacement_m": _float(row.get("boundary_displacement_m")),
            "shape_similarity": _float(row.get("shape_similarity")),
            "overlap_pct_of_cadastral": _float(row.get("overlap_pct_of_cadastral")),
            "perimeter_difference_m": _float(row.get("perimeter_difference_m")),
        }
        am = {
            "survey_number_match": _bool_or_none(row.get("survey_number_match")),
            "land_use_match": _bool_or_none(row.get("land_use_match")),
            "classification_match": _bool_or_none(row.get("classification_match")),
        }
        record = {
            "schema_version": "1.0.0",
            "cadastral_id": (row.get("cadastral_id") or "").strip(),
            "municipal_id": (row.get("municipal_id") or "").strip(),
            "region": (row.get("region") or "unknown").strip(),
            "label": label,
            "review_status": "verified",
            "reviewer": reviewer,
            "evidence_source": f"review-csv:{csv_path.name}",
            "pair_metrics": {"spatial_metrics": sm, "attribute_metrics": am},
            "notes": (row.get("notes_to_fill") or "").strip(),
            "imported_at": datetime.now(timezone.utc).isoformat(),
        }
        try:
            result = append_label(record)
        except LabelStoreError as exc:
            rejected.append((line_no, str(exc)))
            continue
        if result["ok"]:
            imported += 1
        else:
            rejected.append((line_no, result["problems"][0]))

    print(f"Imported : {imported}")
    print(f"Rejected : {len(rejected)}")
    for line_no, reason in rejected[:20]:
        print(f"  line {line_no}: {reason}")
    _, report = load_labels()
    print(f"Store now holds {report['verified_count']} verified labels "
          f"({report.get('label_distribution', {})})")
    return 0 if imported and not rejected else (0 if imported else 1)


def _float(v):
    try:
        return float(v) if v not in (None, "") else None
    except (TypeError, ValueError):
        return None


def _bool_or_none(v):
    s = (v or "").strip().lower()
    if s in ("true", "1", "yes"):
        return True
    if s in ("false", "0", "no"):
        return False
    return None


if __name__ == "__main__":
    sys.exit(main())
