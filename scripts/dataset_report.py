"""
scripts/dataset_report.py
=========================
Dataset quality report over the verified label store (spec §8):
counts, per-class distribution, regions, duplicates, invalid records,
synthetic flags, class imbalance, and provenance.

Exit codes:
    0 — dataset meets training minimums
    3 — INSUFFICIENT_VERIFIED_DATA (reasons printed; training must not run)
    2 — store missing / unreadable

Usage:
    python scripts/dataset_report.py
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

_PROJECT_ROOT = Path(__file__).resolve().parent.parent
for _p in (_PROJECT_ROOT,):
    if str(_p) not in sys.path:
        sys.path.insert(0, str(_p))

from backend.services.label_store import load_labels  # noqa: E402

MIN_PER_CLASS = 10
MIN_TOTAL = 40


def main() -> int:
    records, rep = load_labels()
    if not rep.get("exists"):
        print("LABEL STORE MISSING: data/verified/labels.jsonl does not exist.")
        print("INSUFFICIENT_VERIFIED_DATA — total verified examples: 0")
        return 2

    verified = [r for r in records if r["review_status"] == "verified"]
    usable = [
        r for r in verified
        if r["label"] in ("MATCH", "MINOR_DISCREPANCY", "MAJOR_DISCREPANCY", "UNMATCHED")
    ]

    from collections import Counter

    dist = Counter(r["label"] for r in usable)
    regions = Counter(r["region"] for r in usable)
    reviewers = Counter(r["reviewer"] for r in verified)

    # Duplicate-pair check across the whole store (defensive; store also
    # rejects duplicates on append).
    pairs = Counter((r["cadastral_id"], r["municipal_id"]) for r in records)
    dup_pairs = {k: v for k, v in pairs.items() if v > 1}

    # Missing-feature check over the versioned contract.
    from engine.ml_schema import FEATURE_ORDER, features_from_pair_metrics

    missing_feature_records = 0
    for r in usable:
        feats = features_from_pair_metrics(r.get("pair_metrics", {}))
        if any(v is None for v in feats.values()):
            missing_feature_records += 1

    imbalance = (
        max(dist.values()) / min(dist.values()) if len(dist) >= 2 and min(dist.values()) else None
    )

    print("=== Verified label dataset report ===")
    print(f"Store path            : {rep['path']}")
    print(f"Total lines           : {rep['total_lines']}")
    print(f"Valid records         : {rep['valid_records']}")
    print(f"Invalid records       : {rep['invalid_records']}")
    print(f"Duplicate pairs       : {len(dup_pairs)}")
    print(f"Verified (trainable)  : {len(usable)}")
    print(f"Uncertain / REVIEW    : {rep.get('uncertain_count', 0)}")
    print(f"Labels per class      : {dict(dist)}")
    print(f"Regions               : {dict(regions)}")
    print(f"Reviewers             : {dict(reviewers)}")
    print(f"Missing-feature recs  : {missing_feature_records}")
    print(f"Class imbalance ratio : {imbalance if imbalance is not None else 'n/a'}")
    if rep["problems"]:
        print("Problems:")
        for p in rep["problems"][:15]:
            print(f"  - {p}")

    if len(usable) < MIN_TOTAL or len(dist) < 2 or min(dist.values() or [0]) < MIN_PER_CLASS:
        print("\nINSUFFICIENT_VERIFIED_DATA — training is refused.")
        print(
            f"  Need ≥ {MIN_TOTAL} verified examples, ≥ {MIN_PER_CLASS} per class, "
            f"and at least 2 classes. Have {len(usable)} total, {dict(dist)}."
        )
        return 3

    print("\nDataset meets training minimums.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
