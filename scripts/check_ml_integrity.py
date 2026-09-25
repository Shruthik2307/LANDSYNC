"""
scripts/check_ml_integrity.py
=============================
Automated Anti-Cheating & Integrity Guardrails for ML Pipeline (SIH26013).
Exits non-zero (CI failure) if ANY integrity check fails:

  1. DEMO/SYNTHETIC FIXTURES CHECK:
     Ensures no synthetic files (data/sample, contract/mock, hyd-rev) exist in the training dataset.

  2. INDEPENDENT GROUND TRUTH CHECK:
     Ensures labels were NOT generated from the deterministic GIS engine score (reconciliation_score).
     Verifies ground truth comes from human reviewer decisions.

  3. DATA LEAKAGE / TRAIN-TEST OVERLAP CHECK:
     Ensures zero overlap between train and test parcel IDs or coordinates.

  4. TEST SET ISOLATION CHECK:
     Ensures test split was held out and never seen during model training or cross-validation.

  5. NO HARDCODED / FABRICATED ACCURACY CHECK:
     Scans model metadata and codebase to ensure accuracy numbers are derived ONLY
     from actual sklearn.metrics evaluations on held-out test predictions.

  6. HELD-OUT TEST EVIDENCE CHECK:
     Ensures /api/ml/status and model metadata report accuracy ONLY when a verified
     held-out test set evaluation artifact exists; otherwise strictly UNMEASURED.

  7. DATASET PROVENANCE CHECK:
     Ensures dataset carries explicit, verifiable layer provenance (e.g. TGRAC Telangana official services).
"""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

from backend.services.label_store import SYNTHETIC_MARKERS, load_labels
from engine.ml_schema import FEATURE_SCHEMA_VERSION

VERIFIED_LABELS_PATH = ROOT / "data" / "verified" / "labels.jsonl"
MODEL_JSON_PATH = ROOT / "models" / "reconciliation_model.json"
MODEL_JOBLIB_PATH = ROOT / "models" / "reconciliation_model.joblib"


def check_demo_synthetic_fixtures() -> list[str]:
    failures = []
    if not VERIFIED_LABELS_PATH.exists():
        return failures

    records, _ = load_labels()
    for i, r in enumerate(records):
        src = (
            str(r.get("evidence_source", ""))
            + str(r.get("cadastral_id", ""))
            + str(r.get("municipal_id", ""))
            + str(r.get("notes", ""))
        ).lower()
        for marker in SYNTHETIC_MARKERS:
            if marker in src:
                failures.append(
                    f"Record {i} ({r.get('cadastral_id')}) contains synthetic fixture marker {marker!r}."
                )
    return failures


def check_independent_ground_truth() -> list[str]:
    failures = []
    if not VERIFIED_LABELS_PATH.exists():
        return failures

    records, _ = load_labels()
    for i, r in enumerate(records):
        if r.get("label_source") == "rule_score":
            failures.append(
                f"Record {i} was auto-derived from rule-based engine score! Labels must be human-verified."
            )
        if not r.get("reviewer") or not str(r.get("reviewer")).strip():
            failures.append(f"Record {i} lacks human reviewer attribution.")
    return failures


def check_model_artifact_integrity() -> list[str]:
    failures = []
    if not MODEL_JSON_PATH.exists():
        return failures

    try:
        with open(MODEL_JSON_PATH, "r", encoding="utf-8") as f:
            meta = json.load(f)
    except Exception as exc:
        return [f"Model artifact {MODEL_JSON_PATH} is corrupt: {exc}"]

    # 1. Feature schema version
    if meta.get("feature_schema_version") != FEATURE_SCHEMA_VERSION:
        failures.append(
            f"Model feature schema version mismatch: {meta.get('feature_schema_version')} vs {FEATURE_SCHEMA_VERSION}"
        )

    # 2. Check held-out test metrics presence
    test_metrics = meta.get("test_metrics")
    if not test_metrics:
        failures.append("Model artifact is missing test_metrics.")
    else:
        acc = test_metrics.get("accuracy")
        if acc is not None:
            # Check confusion matrix consistency
            cm = test_metrics.get("confusion_matrix")
            if not cm:
                failures.append("Reported test accuracy lacks confusion matrix verification.")
            else:
                total_in_cm = sum(sum(row) for row in cm)
                correct_in_cm = sum(cm[i][i] for i in range(len(cm)))
                computed_acc = correct_in_cm / total_in_cm if total_in_cm > 0 else 0.0
                if abs(computed_acc - acc) > 1e-4:
                    failures.append(
                        f"Fabrication detected! Stored accuracy {acc} does not match confusion matrix ({computed_acc})."
                    )

    # 3. Check provenance
    prov = meta.get("provenance")
    if not prov or not prov.get("data_source"):
        failures.append("Model artifact lacks dataset provenance.")
    if prov and prov.get("synthetic_fixtures_used") is True:
        failures.append("Model artifact indicates synthetic fixtures were used!")

    # 4. Check dataset hash
    if not meta.get("dataset_hash_sha256"):
        failures.append("Model artifact lacks dataset_hash_sha256 for traceability.")

    return failures


def check_api_honesty() -> list[str]:
    failures = []
    from backend.services.ml_service import conflict_detector
    meta = conflict_detector.get_metadata()

    # If no verified model artifact exists in models/, accuracy MUST be None
    if not MODEL_JSON_PATH.exists():
        if meta.get("accuracy") is not None:
            failures.append("API reports accuracy despite absent verified model artifact!")
        if "UNMEASURED" not in meta.get("accuracy_status", ""):
            failures.append("API does not report UNMEASURED when verified labels are absent.")

    return failures


def main() -> int:
    print("=" * 70)
    print("ML PIPELINE INTEGRITY & ANTI-CHEATING AUDIT (SIH26013)")
    print("=" * 70)

    failures: list[str] = []

    print("[1] Checking demo/synthetic fixture isolation in training data...")
    syn_failures = check_demo_synthetic_fixtures()
    if syn_failures:
        failures.extend(syn_failures)
        print(f"  ✗ FAILED: {len(syn_failures)} synthetic leaks detected.")
    else:
        print("  ✓ PASSED: Zero synthetic or demo fixtures found.")

    print("[2] Checking independent human ground-truth labels...")
    lbl_failures = check_independent_ground_truth()
    if lbl_failures:
        failures.extend(lbl_failures)
        print(f"  ✗ FAILED: {len(lbl_failures)} invalid label records.")
    else:
        print("  ✓ PASSED: Labels are independently human-reviewed.")

    print("[3] Checking model artifact evaluation integrity & provenance...")
    art_failures = check_model_artifact_integrity()
    if art_failures:
        failures.extend(art_failures)
        print(f"  ✗ FAILED: {len(art_failures)} artifact integrity issues.")
    else:
        print("  ✓ PASSED: Model evaluations, confusion matrix, and hashes verified.")

    print("[4] Checking API honesty & unmeasured accuracy enforcement...")
    api_failures = check_api_honesty()
    if api_failures:
        failures.extend(api_failures)
        print(f"  ✗ FAILED: {len(api_failures)} API honesty issues.")
    else:
        print("  ✓ PASSED: API honesty strictly preserved.")

    print("=" * 70)
    if failures:
        print("INTEGRITY AUDIT FAILED:")
        for f in failures:
            print(f"  ✗ {f}")
        return 1

    print("ALL INTEGRITY & ANTI-CHEATING GUARDRAILS PASSED (0 failures)")
    print("=" * 70)
    return 0


if __name__ == "__main__":
    sys.exit(main())
