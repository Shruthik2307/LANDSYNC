"""
scripts/dataset_stats.py
========================
Dataset statistics command for LANDSYNC Real TGRAC Human Ground-Truth Collection.

Reports:
  - Total reviewed
  - Remaining unreviewed
  - Class 0 count (0 = No Conflict / Match)
  - Class 1 count (1 = Minor Discrepancy)
  - Class 2 count (2 = Major/Critical Discrepancy)
  - Class balance (percentages / ratio)
  - Reviewer counts (breakdown by expert reviewer)

Usage:
  python scripts/dataset_stats.py
"""
from __future__ import annotations

import json
import sys
from collections import Counter
from pathlib import Path

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
backend_path = ROOT / "backend"
if str(backend_path) not in sys.path:
    sys.path.insert(0, str(backend_path))

from backend.services.label_store import load_labels

UNREVIEWED_FILE = ROOT / "data" / "unreviewed" / "tgrac_pairs.jsonl"
VERIFIED_FILE = ROOT / "data" / "verified" / "labels.jsonl"


def get_dataset_statistics() -> dict:
    # 1. Total available harvested unreviewed pairs
    total_unreviewed_pool = 0
    if UNREVIEWED_FILE.exists():
        with open(UNREVIEWED_FILE, "r", encoding="utf-8") as f:
            for line in f:
                if line.strip():
                    total_unreviewed_pool += 1

    # 2. Verified labels
    records, rep = load_labels(VERIFIED_FILE)
    verified = [r for r in records if r.get("review_status") == "verified"]

    # Deduplicate verified keys
    verified_keys = {f"{r['cadastral_id']}::{r['municipal_id']}" for r in verified}
    total_reviewed = len(verified_keys)
    remaining = max(0, total_unreviewed_pool - total_reviewed)

    # Class counts
    # Map both string labels and numeric codes to 0, 1, 2
    class_0_labels = {"MATCH", "0", 0, "No Conflict"}
    class_1_labels = {"MINOR_DISCREPANCY", "1", 1, "Minor Discrepancy"}
    class_2_labels = {"MAJOR_DISCREPANCY", "2", 2, "Critical Conflict", "Major Discrepancy"}

    class_0_count = sum(1 for r in verified if r.get("label") in class_0_labels)
    class_1_count = sum(1 for r in verified if r.get("label") in class_1_labels)
    class_2_count = sum(1 for r in verified if r.get("label") in class_2_labels)
    other_count = len(verified) - (class_0_count + class_1_count + class_2_count)

    # Class balance
    counts = [class_0_count, class_1_count, class_2_count]
    if total_reviewed > 0:
        pct_0 = (class_0_count / total_reviewed) * 100
        pct_1 = (class_1_count / total_reviewed) * 100
        pct_2 = (class_2_count / total_reviewed) * 100
        min_c = min(counts)
        max_c = max(counts)
        balance_ratio = f"1 : {(max_c / min_c):.2f}" if min_c > 0 else "imbalanced (has empty classes)"
    else:
        pct_0 = pct_1 = pct_2 = 0.0
        balance_ratio = "n/a (no reviewed samples)"

    # Reviewer counts
    reviewer_counts = Counter(r.get("reviewer", "Unknown") for r in verified)

    return {
        "total_harvested_pool": total_unreviewed_pool,
        "total_reviewed": total_reviewed,
        "remaining": remaining,
        "class_0_count": class_0_count,
        "class_1_count": class_1_count,
        "class_2_count": class_2_count,
        "other_count": other_count,
        "class_balance": {
            "class_0_pct": round(pct_0, 1),
            "class_1_pct": round(pct_1, 1),
            "class_2_pct": round(pct_2, 1),
            "balance_ratio": balance_ratio,
        },
        "reviewer_counts": dict(reviewer_counts),
        "store_path": str(VERIFIED_FILE),
        "unreviewed_path": str(UNREVIEWED_FILE),
    }


def print_dataset_statistics(stats: dict | None = None):
    if stats is None:
        stats = get_dataset_statistics()

    print("=" * 65)
    print("LANDSYNC — REAL TGRAC GROUND-TRUTH DATASET STATISTICS")
    print("=" * 65)
    print(f"Total Harvested Pool : {stats['total_harvested_pool']:,} pairs")
    print(f"Total Reviewed       : {stats['total_reviewed']:,} pairs")
    print(f"Remaining Awaiting   : {stats['remaining']:,} pairs")
    print("-" * 65)
    print("Class Distribution:")
    cb = stats["class_balance"]
    print(f"  Class 0 (No Conflict / Match)        : {stats['class_0_count']:4d}  ({cb['class_0_pct']:5.1f}%)")
    print(f"  Class 1 (Minor Discrepancy)          : {stats['class_1_count']:4d}  ({cb['class_1_pct']:5.1f}%)")
    print(f"  Class 2 (Major/Critical Discrepancy) : {stats['class_2_count']:4d}  ({cb['class_2_pct']:5.1f}%)")
    if stats["other_count"] > 0:
        print(f"  Other / REVIEW                       : {stats['other_count']:4d}")
    print(f"  Class Balance Ratio                  : {cb['balance_ratio']}")
    print("-" * 65)
    print("Reviewer Breakdown:")
    if stats["reviewer_counts"]:
        for reviewer, count in stats["reviewer_counts"].items():
            print(f"  - {reviewer:35s}: {count:4d} labels")
    else:
        print("  (No reviews completed yet)")
    print("=" * 65)

    if stats["total_reviewed"] == 0:
        print("\nNOTE: 0 genuine labels exist. ML accuracy remains UNMEASURED.")
        print("To begin reviewing, run:")
        print("  python scripts/label_expert_cli.py --reviewer \"Your Name\"")
    elif stats["total_reviewed"] < 30 or any(c < 10 for c in [stats["class_0_count"], stats["class_1_count"], stats["class_2_count"]]):
        print(f"\nNOTE: Dataset has {stats['total_reviewed']} labels. Minimum 30 balanced labels (>=10 per class)")
        print("required before verified ML training and held-out evaluation can execute.")
    else:
        print(f"\n✓ Dataset meets minimum criteria for reproducible training ({stats['total_reviewed']} verified labels).")


def main():
    stats = get_dataset_statistics()
    print_dataset_statistics(stats)
    return 0


if __name__ == "__main__":
    sys.exit(main())
