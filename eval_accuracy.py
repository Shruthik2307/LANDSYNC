"""
eval_accuracy.py
================
Honest model evaluation harness (replaces the previous script that
fabricated accuracy from randomly generated synthetic samples — that
practice is prohibited: accuracy reported from synthetic/random data is
not accuracy).

This script does NOT invent labels and does NOT print an accuracy number
unless genuinely labeled, human-verified real evaluation data exists.

Usage
-----
    # 1. Produce labels from human review (never from the rule-based score):
    #    JSON lines, one per parcel pair:
    #    {"iou": 0.92, "area_ratio": 0.97, ..., "verified_label": "MATCH"}
    #    File: data/verified/labels.jsonl
    # 2. Run:
    python eval_accuracy.py data/verified/labels.jsonl

Label vocabulary: MATCH | MINOR_DISCREPANCY | MAJOR_DISCREPANCY |
REVIEW_REQUIRED (human decision, not the engine's).

Output
------
With real labels: accuracy, precision, recall, F1 (macro), per-class
report, confusion matrix — computed with sklearn on the provided data.

Without real labels: prints the honest limitation and exits non-zero.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

from engine.ml_schema import FEATURE_ORDER, features_from_pair_metrics

REQUIRED_SUFFIX = "_verified_label"


def load_labeled_pairs(path: Path) -> list[dict]:
    """Load human-verified labeled parcel pairs from JSON lines."""
    records = []
    with open(path, "r", encoding="utf-8") as f:
        for line_no, line in enumerate(f, start=1):
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            try:
                rec = json.loads(line)
            except json.JSONDecodeError as exc:
                print(f"Line {line_no}: invalid JSON — {exc}")
                continue
            if "pair_metrics" not in rec or "verified_label" not in rec:
                print(f"Line {line_no}: missing pair_metrics or verified_label — skipped")
                continue
            records.append(rec)
    return records


def main() -> int:
    if len(sys.argv) != 2:
        print(__doc__)
        print(
            "ERROR: no labeled evaluation file provided.\n"
            "Accuracy CANNOT be reported without genuinely labeled, unseen, "
            "human-verified real data. The engine score is not a label and "
            "synthetic fixtures are not ground truth."
        )
        return 2

    path = Path(sys.argv[1])
    if not path.exists():
        print(f"ERROR: labeled evaluation file not found: {path}")
        return 2

    records = load_labeled_pairs(path)
    if not records:
        print(
            "ERROR: no usable labeled records found. "
            "Accuracy is NOT reported rather than fabricated."
        )
        return 2

    # Build feature matrix from the recorded pair metrics.
    X, y = [], []
    skipped = 0
    for rec in records:
        feats = features_from_pair_metrics(rec["pair_metrics"])
        if any(v is None for v in feats.values()):
            skipped += 1
            continue
        X.append([feats[k] for k in FEATURE_ORDER])
        y.append(rec["verified_label"])

    if skipped:
        print(f"Note: {skipped} records skipped (missing feature values).")
    if not X:
        print("ERROR: no complete feature vectors — accuracy NOT reported.")
        return 2

    from sklearn.metrics import (
        accuracy_score,
        classification_report,
        confusion_matrix,
        precision_recall_fscore_support,
    )

    from backend.services.ml_service import ConflictDetectionModel  # noqa: F401  (optional)

    # Evaluate against a trained artifact if present; otherwise report that
    # only the labeled dataset statistics can be shown.
    try:
        from backend.services.model_info import get_registry

        registry = get_registry()
        if not registry.available:
            print(
                "MODEL_UNAVAILABLE: no validated model artifact. "
                "Dataset statistics below describe the labels only — "
                "no model accuracy is claimed."
            )
    except Exception:
        pass

    # The actual predictions come from the trained model artifact via the
    # shared predictor; without one, honest dataset statistics are shown.
    try:
        import numpy as np

        from backend.services.reconciliation_model import get_predictor

        predictor = get_predictor()
        if not predictor.available:
            raise RuntimeError("MODEL_UNAVAILABLE")
        preds = [predictor.predict(row)["prediction"] for row in np.asarray(X, dtype=float)]
    except Exception as exc:
        print(f"\nNo production model available for prediction ({exc}).")
        print("Label dataset statistics (NOT model accuracy):")
        from collections import Counter

        for label, count in Counter(y).most_common():
            print(f"  {label}: {count}")
        return 0

    acc = accuracy_score(y, preds)
    precision, recall, f1, _ = precision_recall_fscore_support(
        y, preds, average="macro", zero_division=0
    )
    print("\n=== Held-out evaluation on HUMAN-VERIFIED labels ===")
    print(f"Samples evaluated : {len(y)}")
    print(f"Accuracy          : {acc:.4f}")
    print(f"Precision (macro) : {precision:.4f}")
    print(f"Recall (macro)    : {recall:.4f}")
    print(f"F1 (macro)        : {f1:.4f}")
    print("\nPer-class report:")
    print(classification_report(y, preds, zero_division=0))
    print("Confusion matrix:")
    labels_order = sorted(set(y) | set(preds))
    cm = confusion_matrix(y, preds, labels=labels_order)
    print("      " + "  ".join(f"{l[:12]:>12}" for l in labels_order))
    for label, row in zip(labels_order, cm):
        print(f"{label[:12]:>12}  " + "  ".join(f"{v:>12}" for v in row))
    return 0


if __name__ == "__main__":
    sys.exit(main())
