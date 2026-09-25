"""
backend/tests/test_real_training_pipeline.py
============================================
Automated tests for the real training and verified evaluation pipeline:
  1. Refusal to train on absent or insufficient labels (honest UNMEASURED)
  2. Anti-cheating guardrails (rejection of synthetic fixtures, rule-score targets)
  3. Stratified Train / Held-Out Test split & data leakage prevention
  4. 5-Fold Stratified Cross-Validation on training split
  5. Verified Held-Out Test evaluation (Accuracy, Balanced Accuracy, Macro F1, Confusion Matrix)
  6. Provenance and SHA-256 hash traceability
"""
import hashlib
import json
import numpy as np
import pytest
from pathlib import Path
from sklearn.ensemble import RandomForestClassifier

from backend.services.label_store import append_label, SCHEMA_VERSION
from engine.ml_schema import FEATURE_ORDER
import scripts.train_real_model as trm
import scripts.check_ml_integrity as cmi


def _create_sample_verified_record(cad_id: str, mun_id: str, label: str, reviewer: str = "Expert Surveyor", is_synthetic: bool = False) -> dict:
    source = "data/sample/fixture.geojson" if is_synthetic else "TGRAC_TELANGANA: Cadastral Layer 0 vs Municipal Layer 1"
    # Deterministic spatial metrics
    iou = 0.95 if label == "MATCH" else (0.45 if label == "MINOR_DISCREPANCY" else 0.10)
    area_ratio = 0.98 if label == "MATCH" else (0.60 if label == "MINOR_DISCREPANCY" else 0.20)
    return {
        "schema_version": SCHEMA_VERSION,
        "cadastral_id": cad_id,
        "municipal_id": mun_id,
        "region": "Telangana_Sangareddy",
        "label": label,
        "review_status": "verified",
        "reviewer": reviewer,
        "evidence_source": source,
        "pair_metrics": {
            "spatial_metrics": {
                "iou": iou,
                "area_ratio": area_ratio,
                "area_difference_m2": 50.0,
                "centroid_distance_m": 2.0,
                "hausdorff_distance_m": 5.0,
                "boundary_displacement_m": 1.5,
                "shape_similarity": 0.95,
                "overlap_pct_of_cadastral": 95.0,
                "compactness_difference": 0.02,
                "perimeter_difference_m": 10.0,
                "vertex_count_cadastral": 8,
                "vertex_count_municipal": 8,
            },
            "attribute_metrics": {
                "survey_number_match": True,
                "land_use_match": True,
                "classification_match": True,
            },
        },
        "notes": "Verified ground truth",
    }


class TestHonestStateWhenLabelsAbsent:
    def test_training_stops_honestly_when_labels_absent(self, tmp_path):
        """When data/verified/labels.jsonl is absent or insufficient, accuracy must be UNMEASURED."""
        missing_file = tmp_path / "labels.jsonl"
        res = trm.train_and_evaluate(labels_path=missing_file, dry_run=True)
        assert res["status"] == "INSUFFICIENT_VERIFIED_DATA"
        assert res["accuracy"] is None
        assert "UNMEASURED" in res["accuracy_status"]


class TestAntiCheatingGuardrails:
    def test_synthetic_fixtures_rejected(self):
        """Training pipeline strictly refuses synthetic fixtures."""
        record = _create_sample_verified_record("CAD-001", "MUN-001", "MATCH", is_synthetic=True)
        with pytest.raises(ValueError, match="ANTI-CHEATING VIOLATION"):
            trm.check_anti_cheating([record])

    def test_rule_score_auto_labels_rejected(self):
        """Labels derived from rule engine score are rejected."""
        record = _create_sample_verified_record("CAD-002", "MUN-002", "MATCH")
        record["label_source"] = "rule_score"
        with pytest.raises(ValueError, match="rule-based engine score"):
            trm.check_anti_cheating([record])

    def test_missing_reviewer_rejected(self):
        """Unattributed records are rejected."""
        record = _create_sample_verified_record("CAD-003", "MUN-003", "MATCH", reviewer="")
        with pytest.raises(ValueError, match="verified human reviewer"):
            trm.check_anti_cheating([record])


class TestVerifiedEvaluationMethodology:
    def test_stratified_training_and_held_out_evaluation(self, tmp_path, monkeypatch):
        """When genuine human-verified labels exist, train with 5-fold CV and evaluate on untouched test set."""
        labels_file = tmp_path / "verified_labels.jsonl"

        # Generate 45 realistic, non-synthetic verified records across 3 classes
        records = []
        classes = ["MATCH", "MINOR_DISCREPANCY", "MAJOR_DISCREPANCY"]
        for c in classes:
            for idx in range(15):
                rec = _create_sample_verified_record(
                    cad_id=f"TGRAC-CAD-{c[:3]}-{idx}",
                    mun_id=f"TGRAC-MUN-{c[:3]}-{idx}",
                    label=c,
                    reviewer="Senior Surveyor",
                )
                records.append(rec)
                append_label(rec, path=labels_file)

        monkeypatch.setattr(trm, "MODELS_DIR", tmp_path / "models")
        monkeypatch.setattr(trm, "MODEL_JSON_PATH", tmp_path / "models" / "reconciliation_model.json")
        monkeypatch.setattr(trm, "MODEL_JOBLIB_PATH", tmp_path / "models" / "reconciliation_model.joblib")
        monkeypatch.setattr(trm, "CONFLICT_DETECTOR_PKL", tmp_path / "models" / "conflict_detector.pkl")

        result = trm.train_and_evaluate(labels_path=labels_file, dry_run=False)

        # 1. Verification of execution
        assert result["model_type"] == "RandomForestClassifier"
        assert result["total_samples"] == 45
        assert result["training_samples"] == 36
        assert result["test_samples"] == 9

        # 2. Cross-validation reporting
        cv = result["cross_validation"]
        assert "accuracy_mean" in cv and "accuracy_std" in cv
        assert "f1_macro_mean" in cv
        assert 0.0 <= cv["accuracy_mean"] <= 1.0

        # 3. Held-out test set evaluation
        tm = result["test_metrics"]
        assert "accuracy" in tm
        assert "balanced_accuracy" in tm
        assert "f1_macro" in tm
        assert "confusion_matrix" in tm
        assert len(tm["confusion_matrix"]) == 3

        # 4. Confusion matrix consistency with reported accuracy
        cm = tm["confusion_matrix"]
        total_test = sum(sum(row) for row in cm)
        correct_test = sum(cm[i][i] for i in range(len(cm)))
        assert pytest.approx(correct_test / total_test, 1e-4) == tm["accuracy"]

        # 5. Provenance and Hashes
        assert result["model_hash_sha256"]
        assert result["dataset_hash_sha256"]
        assert result["provenance"]["synthetic_fixtures_used"] is False
        assert result["provenance"]["data_leakage"] is False


class TestIntegrityGuardrailsRunner:
    def test_integrity_guardrails_pass_on_clean_repo(self):
        """scripts/check_ml_integrity.py must pass cleanly on current repo."""
        ret = cmi.main()
        assert ret == 0
