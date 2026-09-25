"""
backend/tests/test_reviewer_workflow.py
=======================================
Tests for the real TGRAC Human Ground-Truth Label Collection and Reviewer Workflow:
  1. Visual 2D parcel footprint rendering (ASCII grid)
  2. Spatial metrics and provenance display
  3. Resume/deduplication support
  4. Dataset statistics command accuracy (total reviewed, remaining, class counts, balance, reviewers)
  5. Reviewer API queue serving real TGRAC pairs with boundaries
  6. Reviewer API label submission with human provenance
  7. Balanced targeting sorting
"""
from __future__ import annotations

import json
from pathlib import Path
import pytest
from fastapi.testclient import TestClient

from backend.main import app
from scripts.dataset_stats import get_dataset_statistics
from scripts.label_expert_cli import (
    render_ascii_overlay,
    sort_for_balanced_targeting,
    LABEL_MAPPING,
)
from backend.services.label_store import SCHEMA_VERSION, append_label, load_labels


@pytest.fixture
def client():
    return TestClient(app)


def test_visual_2d_footprint_rendering():
    """Verify that render_ascii_overlay generates a visual 2D footprint grid."""
    boundaries = {
        "cadastral": {
            "type": "Polygon",
            "coordinates": [[[0, 0], [4, 0], [4, 4], [0, 4], [0, 0]]],
        },
        "municipal": {
            "type": "Polygon",
            "coordinates": [[[2, 2], [6, 2], [6, 6], [2, 6], [2, 2]]],
        },
    }
    rendered = render_ascii_overlay(boundaries, width=30, height=8)
    assert rendered
    # Must contain Cadastral (C), Municipal (M), and Overlap (#) markers
    assert "C" in rendered
    assert "M" in rendered
    assert "#" in rendered
    assert "Cadastral" in rendered
    assert "Municipal" in rendered


def test_dataset_stats_computation(tmp_path, monkeypatch):
    """Verify dataset statistics computation with real unreviewed and verified stores."""
    import scripts.dataset_stats as ds

    unreviewed_file = tmp_path / "tgrac_pairs.jsonl"
    verified_file = tmp_path / "labels.jsonl"

    monkeypatch.setattr(ds, "UNREVIEWED_FILE", unreviewed_file)
    monkeypatch.setattr(ds, "VERIFIED_FILE", verified_file)

    # Write 5 unreviewed pairs
    with open(unreviewed_file, "w", encoding="utf-8") as f:
        for i in range(5):
            f.write(json.dumps({"cadastral_id": f"CAD-{i}", "municipal_id": f"MUN-{i}"}) + "\n")

    # Initial stats: 0 reviewed, 5 remaining
    stats = ds.get_dataset_statistics()
    assert stats["total_harvested_pool"] == 5
    assert stats["total_reviewed"] == 0
    assert stats["remaining"] == 5
    assert stats["class_0_count"] == 0
    assert stats["class_1_count"] == 0
    assert stats["class_2_count"] == 0

    # Add verified labels: 1 Match (0), 1 Minor (1), 1 Major (2)
    classes = [("CAD-0", "MUN-0", "MATCH", "Officer Alice"),
               ("CAD-1", "MUN-1", "MINOR_DISCREPANCY", "Officer Bob"),
               ("CAD-2", "MUN-2", "MAJOR_DISCREPANCY", "Officer Alice")]

    for cad, mun, label, reviewer in classes:
        rec = {
            "schema_version": SCHEMA_VERSION,
            "cadastral_id": cad,
            "municipal_id": mun,
            "region": "Telangana_Sangareddy",
            "label": label,
            "review_status": "verified",
            "reviewer": reviewer,
            "evidence_source": "TGRAC_TELANGANA: Cadastral vs Municipal",
            "pair_metrics": {},
            "notes": "Test verification",
        }
        append_label(rec, path=verified_file)

    stats = ds.get_dataset_statistics()
    assert stats["total_reviewed"] == 3
    assert stats["remaining"] == 2
    assert stats["class_0_count"] == 1
    assert stats["class_1_count"] == 1
    assert stats["class_2_count"] == 1
    assert stats["reviewer_counts"]["Officer Alice"] == 2
    assert stats["reviewer_counts"]["Officer Bob"] == 1
    assert stats["class_balance"]["balance_ratio"] == "1 : 1.00"


def test_tgrac_queue_endpoint_and_resume(client, tmp_path, monkeypatch):
    """Verify /api/labeling/queue?source=tgrac returns unreviewed TGRAC pairs and skips reviewed ones."""
    import sys
    import backend.routes.labeling as brl
    rl = sys.modules.get("routes.labeling", brl)

    unreviewed_file = tmp_path / "tgrac_pairs.jsonl"
    verified_file = tmp_path / "labels.jsonl"

    monkeypatch.setattr(brl, "_UNREVIEWED_FILE", unreviewed_file)
    monkeypatch.setattr(brl, "_VERIFIED_FILE", verified_file)
    monkeypatch.setattr(rl, "_UNREVIEWED_FILE", unreviewed_file)
    monkeypatch.setattr(rl, "_VERIFIED_FILE", verified_file)

    # Seed 3 pairs
    pairs_data = [
        {
            "pair_id": "CAD-101::MUN-101",
            "cadastral_id": "CAD-101",
            "municipal_id": "MUN-101",
            "region": "Telangana_Sangareddy",
            "spatial_metrics": {"iou": 0.95},
            "boundaries": {
                "cadastral": {"type": "Polygon", "coordinates": [[[0, 0], [1, 0], [1, 1], [0, 1], [0, 0]]]},
                "municipal": {"type": "Polygon", "coordinates": [[[0, 0], [1, 0], [1, 1], [0, 1], [0, 0]]]},
            },
            "provenance": {"cadastral_layer": "Bhunaksha_Cadastral Layer 0", "municipal_layer": "Bhunaksha_query Layer 1"},
        },
        {
            "pair_id": "CAD-102::MUN-102",
            "cadastral_id": "CAD-102",
            "municipal_id": "MUN-102",
            "region": "Telangana_Sangareddy",
            "spatial_metrics": {"iou": 0.50},
            "boundaries": {},
            "provenance": {},
        },
    ]
    with open(unreviewed_file, "w", encoding="utf-8") as f:
        for p in pairs_data:
            f.write(json.dumps(p) + "\n")

    # Queue should return both
    resp = client.get("/api/labeling/queue?source=tgrac")
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "ok"
    assert data["count"] == 2
    assert data["pairs"][0]["cadastral_id"] == "CAD-101"
    assert "boundaries" in data["pairs"][0]

    # Submit review for CAD-101
    monkeypatch.setattr("backend.services.label_store.LABELS_PATH", verified_file)
    if "services.label_store" in sys.modules:
        monkeypatch.setattr("services.label_store.LABELS_PATH", verified_file)
    submit_resp = client.post(
        "/api/labeling/submit",
        json={
            "cadastral_id": "CAD-101",
            "municipal_id": "MUN-101",
            "region": "Telangana_Sangareddy",
            "label": "MATCH",
            "reviewer": "Officer_Test",
            "evidence_source": "TGRAC_TELANGANA: Cadastral Layer 0 vs Municipal Layer 1",
            "pair_metrics": {"spatial_metrics": {"iou": 0.95}},
            "notes": "Verified match",
        },
    )
    assert submit_resp.status_code == 200
    assert submit_resp.json()["stored"] is True

    # Queue should now automatically filter out CAD-101 (save/resume)
    resp_after = client.get("/api/labeling/queue?source=tgrac")
    assert resp_after.status_code == 200
    data_after = resp_after.json()
    assert data_after["count"] == 1
    assert data_after["pairs"][0]["cadastral_id"] == "CAD-102"


def test_sort_for_balanced_targeting():
    """Verify sort_for_balanced_targeting interleaves candidates across classes."""
    unlabeled = [
        {"cadastral_id": "1", "spatial_metrics": {"iou": 0.95, "area_ratio": 1.0}},
        {"cadastral_id": "2", "spatial_metrics": {"iou": 0.90, "area_ratio": 1.0}},
        {"cadastral_id": "3", "spatial_metrics": {"iou": 0.50, "area_ratio": 0.7}},
        {"cadastral_id": "4", "spatial_metrics": {"iou": 0.40, "area_ratio": 0.6}},
        {"cadastral_id": "5", "spatial_metrics": {"iou": 0.05, "area_ratio": 0.1}},
        {"cadastral_id": "6", "spatial_metrics": {"iou": 0.10, "area_ratio": 0.2}},
    ]
    interleaved = sort_for_balanced_targeting(unlabeled)
    assert len(interleaved) == 6
    # First 3 should span band 0, band 1, and band 2
    ious = [p["spatial_metrics"]["iou"] for p in interleaved[:3]]
    assert any(iou >= 0.85 for iou in ious)  # class 0 candidate
    assert any(0.30 <= iou < 0.85 for iou in ious)  # class 1 candidate
    assert any(iou < 0.30 for iou in ious)  # class 2 candidate
