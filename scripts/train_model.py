"""
scripts/train_model.py
======================
Train the production reconciliation model — REAL, HUMAN-VERIFIED LABELS ONLY.

Honesty rules enforced here (spec §10/§11/§13):
  * Training data must come from data/verified/ (JSON lines with
    ``verified_label`` set by a human reviewer, never by the rule-based
    engine score, never by synthetic fixture generators).
  * Synthetic fixtures (data/sample/*, contract/mock/*) are rejected —
    CI blocks any run that tries to train on them.
  * The script refuses to run entirely if the labeled dataset is absent
    or too small, printing the limitation instead of fabricating a model.

Methodology (executed when real labels exist):
  * Geographic holdout: records carry an optional ``region`` field;
    splits are grouped by region (train/val/test on DISJOINT areas) so
    near-duplicate geography cannot leak across splits (spec §11).
  * Multiple algorithms compared by macro-F1 on the validation split.
  * The untouched grouped test split produces the ONLY reported test
    metrics; it is never used for tuning.

Artifact: models/reconciliation_model.json + training_metadata.json
(loaded/validated by backend/services/model_info.py).
"""

from __future__ import annotations

import json
import sys
from datetime import datetime, timezone
from pathlib import Path

_PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(_PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(_PROJECT_ROOT))

from engine.ml_schema import FEATURE_ORDER, FEATURE_SCHEMA_VERSION, features_from_pair_metrics

VERIFIED_DIR = _PROJECT_ROOT / "data" / "verified"
LABELS_PATH = VERIFIED_DIR / "labels.jsonl"
MODELS_DIR = _PROJECT_ROOT / "models"
ARTIFACT_PATH = MODELS_DIR / "reconciliation_model.json"
METADATA_PATH = MODELS_DIR / "training_metadata.json"

# Minimum labeled samples per class before training is allowed. Below this
# the honest answer is "not enough verified data", not a tiny model.
MIN_SAMPLES_PER_CLASS = 10

FORBIDDEN_PATH_MARKERS = ("sample", "mock", "fixture", "synthetic")


def load_verified_labels() -> list[dict]:
    """Load human-verified labeled records; reject anything suspicious."""
    if not LABELS_PATH.exists():
        return []
    records = []
    with open(LABELS_PATH, "r", encoding="utf-8") as f:
        for line_no, line in enumerate(f, start=1):
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            try:
                rec = json.loads(line)
            except json.JSONDecodeError:
                print(f"  line {line_no}: invalid JSON — skipped")
                continue
            if "pair_metrics" not in rec or "verified_label" not in rec:
                print(f"  line {line_no}: missing pair_metrics/verified_label — skipped")
                continue
            records.append(rec)
    return records


def assert_not_synthetic(records: list[dict]) -> None:
    """Guardrail: reject records that carry synthetic/provenance markers."""
    for i, rec in enumerate(records):
        src = str(rec.get("source", "")) + str(rec.get("dataset", ""))
        if any(marker in src.lower() for marker in FORBIDDEN_PATH_MARKERS):
            raise SystemExit(
                f"REFUSING TO TRAIN: record {i} carries a synthetic-data marker "
                f"({src!r}). Training on synthetic fixtures is prohibited (spec §10)."
            )


def build_matrix(records: list[dict]):
    """Feature matrix + label vector; records with unknown features dropped."""
    X, y, regions = [], [], []
    for rec in records:
        feats = features_from_pair_metrics(rec["pair_metrics"])
        if any(v is None for v in feats.values()):
            continue
        X.append([float(feats[k]) for k in FEATURE_ORDER])
        y.append(str(rec["verified_label"]))
        regions.append(str(rec.get("region", "unknown")))
    return X, y, regions


def main() -> int:
    print("=== LANDSYNC production model training (honest mode) ===")
    records = load_verified_labels()
    if not records:
        print(
            f"REFUSING TO TRAIN: no human-verified labeled records found at\n"
            f"  {LABELS_PATH}\n"
            "Labels must be produced by human review of REAL parcel pairs —\n"
            "never from the rule-based score, never from synthetic fixtures.\n"
            "The system continues to run on deterministic GIS evidence alone,\n"
            "and /api/model/info reports MODEL_UNAVAILABLE honestly."
        )
        return 2

    assert_not_synthetic(records)

    from collections import Counter

    label_counts = Counter(str(r["verified_label"]) for r in records)
    print(f"Labeled records: {len(records)}  distribution: {dict(label_counts)}")
    if min(label_counts.values()) < MIN_SAMPLES_PER_CLASS:
        print(
            "REFUSING TO TRAIN: fewer than "
            f"{MIN_SAMPLES_PER_CLASS} verified samples per class. "
            "Gather more human-verified labels — no model will be published, "
            "and no accuracy will be fabricated from insufficient data."
        )
        return 2

    X, y, regions = build_matrix(records)
    if not X:
        print("REFUSING TO TRAIN: no complete feature vectors in labeled data.")
        return 2

    import numpy as np
    from sklearn.ensemble import (
        ExtraTreesClassifier,
        GradientBoostingClassifier,
        RandomForestClassifier,
    )
    from sklearn.linear_model import LogisticRegression
    from sklearn.metrics import f1_score
    from sklearn.model_selection import GroupKFold, cross_val_score
    from sklearn.preprocessing import StandardScaler
    from sklearn.pipeline import Pipeline

    X_arr, y_arr = np.asarray(X), np.asarray(y)
    regions_arr = np.asarray(regions)

    # ---- Geographic holdout: grouped splits by region (spec §11) ----------
    groups = regions_arr
    n_groups = len(set(groups))
    if n_groups < 3:
        print(
            f"WARNING: only {n_groups} distinct region(s) in labeled data — "
            "true geographic holdout is not possible; grouped CV still used."
        )
        n_splits = max(2, min(n_groups, 5))
    else:
        n_splits = 3
    gkf = GroupKFold(n_splits=n_splits)
    splits = list(gkf.split(X_arr, y_arr, groups=groups))
    train_idx, test_idx = splits[0]  # untouched final holdout
    # Carve validation out of the training portion by group as well.
    val_gkf = GroupKFold(n_splits=2)
    tr_idx, va_idx = next(val_gkf.split(X_arr[train_idx], y_arr[train_idx],
                                       groups=groups[train_idx]))
    tr_idx = train_idx[tr_idx]
    va_idx = train_idx[va_idx]

    candidates = {
        "logistic_regression": Pipeline([
            ("scaler", StandardScaler()),
            ("clf", LogisticRegression(max_iter=2000, class_weight="balanced")),
        ]),
        "random_forest": RandomForestClassifier(
            n_estimators=300, class_weight="balanced", random_state=42
        ),
        "extra_trees": ExtraTreesClassifier(
            n_estimators=300, class_weight="balanced", random_state=42
        ),
        "gradient_boosting": GradientBoostingClassifier(random_state=42),
    }

    comparison = {}
    for name, model in candidates.items():
        try:
            model.fit(X_arr[tr_idx], y_arr[tr_idx])
            val_pred = model.predict(X_arr[va_idx])
            comparison[name] = {
                "validation_f1_macro": float(
                    f1_score(y_arr[va_idx], val_pred, average="macro", zero_division=0)
                ),
                "validation_accuracy": float(
                    (val_pred == y_arr[va_idx]).mean()
                ),
            }
        except Exception as exc:
            comparison[name] = {"error": str(exc)}
    print("Model comparison (validation split):")
    for name, m in comparison.items():
        print(f"  {name}: {m}")

    usable = {k: v for k, v in comparison.items() if "validation_f1_macro" in v}
    if not usable:
        print("REFUSING TO TRAIN: all candidate models failed on validation split.")
        return 2
    best_name = max(usable, key=lambda k: usable[k]["validation_f1_macro"])
    best_model = candidates[best_name]

    # Grouped CV for stability (still excludes the untouched test split).
    try:
        cv_f1 = cross_val_score(
            best_model, X_arr[tr_idx], y_arr[tr_idx],
            groups=groups[tr_idx], cv=gkf, scoring="f1_macro",
        )
        cv_f1 = [float(v) for v in cv_f1]
    except Exception:
        cv_f1 = []

    # ---- Final untouched test evaluation (geographic holdout) -------------
    from sklearn.metrics import (
        accuracy_score,
        classification_report,
        confusion_matrix,
        precision_recall_fscore_support,
    )

    best_model.fit(X_arr[tr_idx], y_arr[tr_idx])

    # Persist the fitted estimator + per-feature training stats for the
    # serving-layer OOD guard (backend/services/reconciliation_model.py).
    import joblib

    feature_stats = {}
    for j, feat_name in enumerate(FEATURE_ORDER):
        col = X_arr[tr_idx][:, j]
        feature_stats[feat_name] = {
            "mean": float(col.mean()),
            "std": float(col.std()),
            "min": float(col.min()),
            "max": float(col.max()),
        }
    MODELS_DIR.mkdir(parents=True, exist_ok=True)
    joblib.dump(best_model, MODELS_DIR / "reconciliation_model.joblib")

    test_pred = best_model.predict(X_arr[test_idx])
    acc = float(accuracy_score(y_arr[test_idx], test_pred))
    precision, recall, f1, _ = precision_recall_fscore_support(
        y_arr[test_idx], test_pred, average="macro", zero_division=0
    )
    labels_order = sorted(set(y_arr.tolist()))
    cm = confusion_matrix(y_arr[test_idx], test_pred, labels=labels_order)

    print("\n=== FINAL geographic-holdout test (untouched) ===")
    print(f"Accuracy   : {acc:.4f}")
    print(f"Precision  : {precision:.4f} (macro)")
    print(f"Recall     : {recall:.4f} (macro)")
    print(f"F1 (macro) : {f1:.4f}")
    print("Confusion matrix (rows=true, cols=pred):")
    print(classification_report(y_arr[test_idx], test_pred, zero_division=0))

    artifact = {
        "model_version": datetime.now(timezone.utc).strftime("v%Y.%m.%d.%H%M"),
        "model_type": best_name,
        "training_date": datetime.now(timezone.utc).isoformat(),
        "training_sample_count": int(len(tr_idx)),
        "verified_label_count": int(len(records)),
        "feature_schema_version": FEATURE_SCHEMA_VERSION,
        "feature_order": list(FEATURE_ORDER),
        "validation_metrics": comparison[best_name],
        "model_comparison": comparison,
        "cv_f1_macro_folds": cv_f1,
        "test_metrics": {
            "accuracy": acc,
            "precision_macro": float(precision),
            "recall_macro": float(recall),
            "f1_macro": float(f1),
            "support": int(len(test_idx)),
            "labels": labels_order,
            "confusion_matrix": cm.tolist(),
        },
        "geographic_holdout_metrics": {
            "method": "GroupKFold by region",
            "regions": sorted(set(groups.tolist())),
            "test_region_support": int(len(test_idx)),
            "accuracy": acc,
            "f1_macro": float(f1),
        },
        "feature_stats": feature_stats,
        "training_class_distribution": dict(label_counts),
        "calibration_status": "uncalibrated",
        "production_status": "active",
    }

    MODELS_DIR.mkdir(parents=True, exist_ok=True)
    with open(ARTIFACT_PATH, "w", encoding="utf-8") as f:
        json.dump(artifact, f, indent=2)
    with open(METADATA_PATH, "w", encoding="utf-8") as f:
        json.dump(
            {
                "labels_path": str(LABELS_PATH),
                "trained_at": artifact["training_date"],
                "model_version": artifact["model_version"],
            },
            f,
            indent=2,
        )
    print(f"\nArtifact written: {ARTIFACT_PATH}")
    print("Model registry will validate it at next backend start.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
