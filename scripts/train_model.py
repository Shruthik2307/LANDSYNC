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

from engine.ml_schema import FEATURE_ORDER, FEATURE_SCHEMA_VERSION, features_from_pair_metrics  # noqa: E402
from scripts.label_store import load_labels, verified_training_records  # noqa: E402

VERIFIED_DIR = _PROJECT_ROOT / "data" / "verified"
LABELS_PATH = VERIFIED_DIR / "labels.jsonl"
MODELS_DIR = _PROJECT_ROOT / "models"
ARTIFACT_PATH = MODELS_DIR / "reconciliation_model.json"
METADATA_PATH = MODELS_DIR / "training_metadata.json"
ESTIMATOR_PATH = MODELS_DIR / "reconciliation_model.joblib"

# Minimum labeled samples per class before training is allowed. Below this
# the honest answer is INSUFFICIENT_VERIFIED_DATA, not a tiny model.
MIN_SAMPLES_PER_CLASS = 10
MIN_TOTAL = 40

FORBIDDEN_PATH_MARKERS = ("sample", "mock", "fixture", "synthetic", "hyd-rev")


def _data_version() -> str:
    """Stable hash of the label store contents (dataset versioning, §17)."""
    import hashlib

    if not LABELS_PATH.exists():
        return "no-labels"
    return hashlib.sha256(LABELS_PATH.read_bytes()).hexdigest()[:16]


def load_verified_labels() -> list[dict]:
    """Load verified, usable labels via the shared validated store."""
    records, rep = load_labels()
    if rep.get("invalid_records") or rep.get("duplicate_pairs"):
        print(
            f"Label store problems: {rep['invalid_records']} invalid, "
            f"{rep['duplicate_pairs']} duplicate — fix data/verified/labels.jsonl."
        )
    return verified_training_records(records)


def assert_not_synthetic(records: list[dict]) -> None:
    """Guardrail: reject records that carry synthetic/provenance markers."""
    for i, rec in enumerate(records):
        src = (
            str(rec.get("evidence_source", ""))
            + str(rec.get("cadastral_id", ""))
            + str(rec.get("municipal_id", ""))
            + str(rec.get("notes", ""))
        )
        if any(marker in src.lower() for marker in FORBIDDEN_PATH_MARKERS):
            raise SystemExit(
                f"REFUSING TO TRAIN: record {i} carries a synthetic-data marker "
                f"({src!r}). Training on synthetic fixtures is prohibited (spec §2)."
            )


def build_matrix(records: list[dict]):
    """Feature matrix + label vector; records with unknown features dropped."""
    X, y, regions = [], [], []
    for rec in records:
        feats = features_from_pair_metrics(rec["pair_metrics"])
        if any(v is None for v in feats.values()):
            continue
        X.append([float(feats[k]) for k in FEATURE_ORDER])
        y.append(str(rec["label"]))
        regions.append(str(rec.get("region", "unknown")))
    return X, y, regions


def main() -> int:
    print("=== LANDSYNC production model training (honest mode) ===")
    records = load_verified_labels()
    from collections import Counter

    if not records:
        print(
            f"ML MODEL NOT TRAINED — INSUFFICIENT VERIFIED DATA.\n"
            f"No human-verified training labels found at\n  {LABELS_PATH}\n"
            "Labels must be produced by human review of REAL parcel pairs —\n"
            "never from the rule-based score, never from synthetic fixtures.\n"
            "Use the labeling workflow: backend /api/labeling/queue + submit,\n"
            "or scripts/export_review_queue.py + scripts/import_verified_labels.py.\n"
            "The system continues to run on deterministic GIS evidence alone,\n"
            "and /api/model/info reports MODEL_UNAVAILABLE honestly."
        )
        return 3

    assert_not_synthetic(records)

    label_counts = Counter(str(r["label"]) for r in records)
    print(f"Verified training records: {len(records)}  distribution: {dict(label_counts)}")
    if len(records) < MIN_TOTAL or min(label_counts.values()) < MIN_SAMPLES_PER_CLASS:
        print(
            "INSUFFICIENT_VERIFIED_DATA — training is refused.\n"
            f"  Need ≥ {MIN_TOTAL} records and ≥ {MIN_SAMPLES_PER_CLASS} per class; "
            f"have {len(records)} total, {dict(label_counts)}.\n"
            "No model artifact will be produced and no metrics will be fabricated."
        )
        return 3

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
    joblib.dump(best_model, ESTIMATOR_PATH)

    test_pred = best_model.predict(X_arr[test_idx])
    acc = float(accuracy_score(y_arr[test_idx], test_pred))
    precision, recall, f1, _ = precision_recall_fscore_support(
        y_arr[test_idx], test_pred, average="macro", zero_division=0
    )
    _, _, f1_w, _ = precision_recall_fscore_support(
        y_arr[test_idx], test_pred, average="weighted", zero_division=0
    )
    from sklearn.metrics import balanced_accuracy_score

    balanced_acc = float(balanced_accuracy_score(y_arr[test_idx], test_pred))
    labels_order = sorted(set(y_arr.tolist()))
    cm = confusion_matrix(y_arr[test_idx], test_pred, labels=labels_order)

    # ---- Discrepancy recall (spec §12): recall on discrepancy classes -----
    from sklearn.metrics import recall_score

    discrepancy_mask = np.isin(
        y_arr[test_idx], ["MINOR_DISCREPANCY", "MAJOR_DISCREPANCY"]
    )
    if discrepancy_mask.any():
        y_true_bin = np.where(discrepancy_mask, "DISCREPANCY", "OTHER")
        y_pred_bin = np.where(
            np.isin(test_pred, ["MINOR_DISCREPANCY", "MAJOR_DISCREPANCY"]),
            "DISCREPANCY",
            "OTHER",
        )
        discrepancy_recall = float(
            recall_score(y_true_bin, y_pred_bin, pos_label="DISCREPANCY", zero_division=0)
        )
    else:
        discrepancy_recall = None

    # ---- Probability calibration (spec §13): fit on validation split -----
    calibration_status = "not_applicable"
    calibrated_metrics = None
    try:
        from sklearn.calibration import CalibratedClassifierCV

        if hasattr(best_model, "predict_proba") and len(va_idx) >= 10:
            calibrated = CalibratedClassifierCV(best_model, method="sigmoid", cv="prefit")
            calibrated.fit(X_arr[va_idx], y_arr[va_idx])
            cal_proba = calibrated.predict_proba(X_arr[va_idx])
            cal_pred = calibrated.classes_[np.argmax(cal_proba, axis=1)]
            calibration_f1 = float(
                f1_score(y_arr[va_idx], cal_pred, average="macro", zero_division=0)
            )
            calibration_status = "sigmoid_on_validation_split"
            calibrated_metrics = {
                "method": "sigmoid (Platt), fit on validation split",
                "validation_f1_macro_after_calibration": calibration_f1,
            }
            joblib.dump(calibrated, ESTIMATOR_PATH)  # serve calibrated pipeline
    except Exception as exc:
        calibration_status = f"failed: {exc}"

    print("\n=== FINAL geographic-holdout test (untouched) ===")
    print(f"Accuracy              : {acc:.4f}")
    print(f"Balanced accuracy     : {balanced_acc:.4f}")
    print(f"Precision (macro)     : {precision:.4f}")
    print(f"Recall (macro)        : {recall:.4f}")
    print(f"F1 (macro)            : {f1:.4f}")
    if discrepancy_recall is not None:
        print(f"Discrepancy recall    : {discrepancy_recall:.4f}")
    print("Confusion matrix (rows=true, cols=pred):")
    print(classification_report(y_arr[test_idx], test_pred, zero_division=0))

    artifact = {
        "model_version": datetime.now(timezone.utc).strftime("v%Y.%m.%d.%H%M"),
        "model_type": best_name,
        "training_date": datetime.now(timezone.utc).isoformat(),
        "training_sample_count": int(len(tr_idx)),
        "verified_label_count": int(len(records)),
        "verified_sample_count": int(len(records)),
        "class_distribution": dict(label_counts),
        "feature_schema_version": FEATURE_SCHEMA_VERSION,
        "feature_order": list(FEATURE_ORDER),
        "validation_metrics": comparison[best_name],
        "model_comparison": comparison,
        "cv_f1_macro_folds": cv_f1,
        "test_metrics": {
            "accuracy": acc,
            "balanced_accuracy": float(balanced_acc),
            "precision_macro": float(precision),
            "recall_macro": float(recall),
            "f1_macro": float(f1),
            "f1_weighted": float(f1_weighted),
            "discrepancy_recall": discrepancy_recall,
            "support": int(len(test_idx)),
            "labels": labels_order,
            "confusion_matrix": cm.tolist(),
        },
        "geographic_holdout_metrics": {
            "method": "GroupKFold by region (train/val/test disjoint)",
            "regions": sorted(set(groups.tolist())),
            "test_region_support": int(len(test_idx)),
            "accuracy": acc,
            "f1_macro": float(f1),
        },
        "feature_stats": feature_stats,
        "training_class_distribution": dict(label_counts),
        "calibration_status": calibration_status,
        "calibration_metrics": calibrated_metrics,
        "training_data_version": _data_version(),
        "production_status": "active",
    }

    MODELS_DIR.mkdir(parents=True, exist_ok=True)
    with open(ARTIFACT_PATH, "w", encoding="utf-8") as f:
        json.dump(artifact, f, indent=2)
    with open(METADATA_PATH, "w", encoding="utf-8") as f:
        json.dump(
            {
                "labels_path": str(LABELS_PATH),
                "labels_sha256_16": _data_version(),
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
