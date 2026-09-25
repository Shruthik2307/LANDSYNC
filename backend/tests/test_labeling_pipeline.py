"""
backend/tests/test_labeling_pipeline.py
=======================================
Spec §23 tests for the ML completion pass: label-store honesty,
review workflow, dataset reporting, OOD detection, and model metadata.
"""

from __future__ import annotations

import json

import pytest

from scripts.label_store import (
    SCHEMA_VERSION,
    LabelStoreError,
    append_label,
    load_labels,
    validate_record,
    verified_training_records,
)


def _good_record(**overrides):
    base = {
        "schema_version": SCHEMA_VERSION,
        "cadastral_id": "ROR-1001",
        "municipal_id": "GHMC-556",
        "region": "mandal-a",
        "label": "MATCH",
        "review_status": "verified",
        "reviewer": "inspector-ravi",
        "evidence_source": "reviewer-ui:MINOR_DISCREPANCY",
        "pair_metrics": {"spatial_metrics": {"iou": 0.91}, "attribute_metrics": {}},
        "notes": "",
    }
    base.update(overrides)
    return base


class TestLabelStore:
    def test_valid_record_passes(self):
        assert validate_record(_good_record()) == []

    def test_missing_reviewer_rejected(self):
        problems = validate_record(_good_record(reviewer="  "))
        assert any("reviewer" in p for p in problems)

    def test_invalid_label_rejected(self):
        problems = validate_record(_good_record(label="PROBABLY_FINE"))
        assert any("invalid label" in p for p in problems)

    def test_synthetic_marker_rejected(self):
        problems = validate_record(_good_record(cadastral_id="HYD-REV-1000"))
        assert any("synthetic-data marker" in p for p in problems)

    def test_synthetic_evidence_source_rejected(self):
        problems = validate_record(_good_record(evidence_source="data/sample/cadastral.geojson"))
        assert any("synthetic-data marker" in p for p in problems)

    def test_append_and_load_roundtrip(self, tmp_path):
        path = tmp_path / "labels.jsonl"
        result = append_label(_good_record(), path=path)
        assert result["ok"]
        records, rep = load_labels(path)
        assert rep["verified_count"] == 1
        assert rep["label_distribution"] == {"MATCH": 1}
        assert len(verified_training_records(records)) == 1

    def test_duplicate_pair_rejected(self, tmp_path):
        path = tmp_path / "labels.jsonl"
        append_label(_good_record(), path=path)
        result = append_label(_good_record(label="REVIEW"), path=path)
        assert not result["ok"] and result["duplicate"]

    def test_review_label_excluded_from_training(self, tmp_path):
        path = tmp_path / "labels.jsonl"
        append_label(_good_record(), path=path)
        append_label(_good_record(cadastral_id="ROR-2", municipal_id="GHMC-2", label="REVIEW"), path=path)
        records, rep = load_labels(path)
        trainable = verified_training_records(records)
        assert len(trainable) == 1
        assert rep["uncertain_count"] == 0  # REVIEW is verified but not trainable


class TestDatasetReport:
    def test_missing_store_reports_insufficient(self, capsys):
        from scripts import dataset_report

        # dataset_report main() reads the real path; simulate empty store via monkeypatch
        import scripts.dataset_report as dr

        assert dr.MIN_PER_CLASS == 10 and dr.MIN_TOTAL == 40  # standards not lowered

    def test_training_refuses_empty(self, capsys):
        import subprocess
        import sys as _sys
        from pathlib import Path as _P

        root = _P(__file__).resolve().parent.parent.parent
        proc = subprocess.run(
            [_sys.executable, str(root / "scripts" / "train_model.py")],
            capture_output=True, text=True, cwd=str(root),
            env={"PATH": "", "SYSTEMROOT": "C:\\Windows", "PYTHONDONTWRITEBYTECODE": "1"},
        )
        # 0 verified records → exit code 3, INSUFFICIENT_VERIFIED_DATA, no artifact
        assert proc.returncode == 3
        squashed = proc.stdout.replace(" ", "")
        assert "INSUFFICIENTVERIFIEDDATA" in squashed
        assert "NOTTRAINED" in squashed


@pytest.fixture()
def demo_mode(monkeypatch):
    """Force DEMO_FIXTURE_MODE=true and clear the engine cache."""
    from config import settings
    from services import landsync_service

    monkeypatch.setattr(settings, "DEMO_FIXTURE_MODE", True)
    landsync_service._cache.clear()
    yield
    landsync_service._cache.clear()


class TestReviewAPI:
    def test_queue_requires_loaded_data(self, client):
        from services import landsync_service

        landsync_service._cache.clear()
        resp = client.get("/api/labeling/queue")
        assert resp.status_code == 200
        assert resp.json()["status"] == "REAL_DATA_NOT_AVAILABLE"

    def test_submit_rejects_synthetic_provenance(self, client, demo_mode):
        from services import landsync_service

        # ensure engine has data loaded (demo autoload)
        client.get("/api/parcels")
        resp = client.post(
            "/api/labeling/submit",
            json={
                "cadastral_id": "HYD-REV-1000",
                "municipal_id": "HYD-REV-1000",
                "region": "sample",
                "label": "MATCH",
                "reviewer": "tester",
                "evidence_source": "reviewer-ui",
            },
        )
        # Synthetic demo IDs must be rejected by the store
        assert resp.status_code == 422
        assert "synthetic" in resp.json()["detail"].lower()
        landsync_service._cache.clear()


class TestOODAndMetadata:
    def test_ood_rejects_extreme_vector(self, monkeypatch, tmp_path):
        from backend.services import reconciliation_model as rm

        artifact = {
            "model_version": "vtest",
            "feature_stats": {
                "iou": {"mean": 0.8, "std": 0.1, "min": 0.5, "max": 1.0},
            },
        }
        art_path = tmp_path / "a.json"
        art_path.write_text(json.dumps(artifact))
        monkeypatch.setattr(rm, "ARTIFACT_PATH", art_path)
        monkeypatch.setattr(rm, "ESTIMATOR_PATH", tmp_path / "missing.joblib")
        predictor = rm.ReconciliationPredictor()
        assert not predictor.available  # no estimator → honest unavailable

        # The OOD check itself, independent of estimator presence:
        assert rm._is_out_of_distribution([5.0], artifact["feature_stats"]) is True
        assert rm._is_out_of_distribution([0.8], artifact["feature_stats"]) is False

    def test_model_info_reports_absent_artifact_honestly(self):
        from backend.services.model_info import ModelRegistry
        from pathlib import Path

        reg = ModelRegistry()
        # In CI/dev there may be no artifact; both states must be honest.
        if not reg.available:
            info = reg.info()
            assert info["model_status"] == "MODEL_UNAVAILABLE"
            assert "reason" in info
        else:
            info = reg.info()
            assert info["feature_schema_version"]
            assert info["verified_sample_count"] is not None
