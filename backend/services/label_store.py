"""
backend/services/label_store.py
===============================
Label store for human-verified reconciliation labels (spec §3, §4).

Storage: data/verified/labels.jsonl — one JSON object per line.

Record schema (all fields required except notes):
    {
      "schema_version":  "1.0.0",
      "cadastral_id":    str,
      "municipal_id":    str,
      "region":          str,
      "label":           "MATCH" | "MINOR_DISCREPANCY" | "MAJOR_DISCREPANCY"
                         | "UNMATCHED" | "REVIEW",
      "review_status":   "verified" | "uncertain",
      "reviewer":        str,
      "evidence_source": str,
      "pair_metrics":    { ... engine.metrics output ... },
      "notes":           str (optional)
    }

Rules enforced here (spec §2/§21):
  * Only records with review_status == "verified" and a human reviewer
    name count as training labels.
  * Synthetic provenance markers are rejected on write and flagged on
    load — synthetic data must never enter training.
  * Duplicate (cadastral_id, municipal_id) pairs are rejected on append
    and flagged on load.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any, Optional

_PROJECT_ROOT = Path(__file__).resolve().parent.parent
LABELS_PATH = _PROJECT_ROOT / "data" / "verified" / "labels.jsonl"

SCHEMA_VERSION = "1.0.0"

VALID_LABELS = (
    "MATCH",
    "MINOR_DISCREPANCY",
    "MAJOR_DISCREPANCY",
    "UNMATCHED",
    "REVIEW",
)
VALID_REVIEW_STATUS = ("verified", "uncertain")

SYNTHETIC_MARKERS = ("sample", "mock", "fixture", "synthetic", "hyd-rev")
# Note: hyd-rev is the ID prefix of the bundled demo parcels (case-insensitive match).

REQUIRED_FIELDS = (
    "schema_version",
    "cadastral_id",
    "municipal_id",
    "region",
    "label",
    "review_status",
    "reviewer",
    "evidence_source",
    "pair_metrics",
)


class LabelStoreError(ValueError):
    """Raised when a label record violates the schema or honesty rules."""


def validate_record(record: dict, *, line_no: Optional[int] = None) -> list[str]:
    """Return a list of problems (empty = valid)."""
    where = f"line {line_no}: " if line_no is not None else ""
    problems: list[str] = []

    for field in REQUIRED_FIELDS:
        if field not in record or record[field] in (None, ""):
            problems.append(f"{where}missing required field {field!r}")
    if problems:
        return problems

    if record["schema_version"] != SCHEMA_VERSION:
        problems.append(
            f"{where}schema_version {record['schema_version']!r} != {SCHEMA_VERSION!r}"
        )
    if record["label"] not in VALID_LABELS:
        problems.append(f"{where}invalid label {record['label']!r}")
    if record["review_status"] not in VALID_REVIEW_STATUS:
        problems.append(f"{where}invalid review_status {record['review_status']!r}")
    if record["review_status"] == "verified" and not str(record["reviewer"]).strip():
        problems.append(f"{where}verified record requires a named reviewer")
    if not isinstance(record.get("pair_metrics"), dict):
        problems.append(f"{where}pair_metrics must be an object")

    provenance = (
        str(record.get("evidence_source", ""))
        + str(record.get("cadastral_id", ""))
        + str(record.get("municipal_id", ""))
        + str(record.get("notes", ""))
    ).lower()
    for marker in SYNTHETIC_MARKERS:
        if marker in provenance:
            problems.append(
                f"{where}synthetic-data marker {marker!r} in provenance fields "
                "(synthetic data must never become training labels)"
            )
    return problems


def append_label(record: dict, *, path: Path = LABELS_PATH, strict: bool = True) -> dict:
    """Validate and append one label record.

    Returns {"ok": bool, "problems": [...], "duplicate": bool}.
    With strict=True, schema violations raise LabelStoreError.
    """
    problems = validate_record(record)
    if problems and strict:
        raise LabelStoreError("; ".join(problems))

    path.parent.mkdir(parents=True, exist_ok=True)
    duplicate = False
    if path.exists():
        key = (str(record.get("cadastral_id")), str(record.get("municipal_id")))
        for existing in _iter_records(path):
            if (str(existing.get("cadastral_id")), str(existing.get("municipal_id"))) == key:
                duplicate = True
                break
    if duplicate:
        return {"ok": False, "problems": ["duplicate (cadastral_id, municipal_id) pair"], "duplicate": True}

    with open(path, "a", encoding="utf-8") as f:
        f.write(json.dumps(record, ensure_ascii=False) + "\n")
    return {"ok": True, "problems": problems, "duplicate": False}


def _iter_records(path: Path):
    with open(path, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                yield json.loads(line)


def load_labels(
    path: Path = LABELS_PATH,
) -> tuple[list[dict], dict]:
    """Load all records plus a validation report.

    Report includes counts, per-class distribution, duplicates, invalid
    lines, synthetic-marker records, and verified-only counts. Records
    with problems are EXCLUDED from the returned list but described in
    the report (spec §8: dataset quality report before training).
    """
    report: dict[str, Any] = {
        "path": str(path),
        "exists": path.exists(),
        "total_lines": 0,
        "valid_records": 0,
        "invalid_records": 0,
        "duplicate_pairs": 0,
        "synthetic_flagged": 0,
        "verified_count": 0,
        "uncertain_count": 0,
        "label_distribution": {},
        "regions": [],
        "problems": [],
    }
    if not path.exists():
        return [], report

    records: list[dict] = []
    seen_pairs: set[tuple[str, str]] = set()
    regions: set[str] = set()

    for line_no, raw in enumerate(_iter_records(path), start=1):
        report["total_lines"] += 1
        try:
            record = raw
        except json.JSONDecodeError:
            report["invalid_records"] += 1
            report["problems"].append(f"line {line_no}: invalid JSON")
            continue

        problems = validate_record(record, line_no=line_no)
        if problems:
            report["invalid_records"] += 1
            report["problems"].extend(problems)
            continue

        key = (str(record["cadastral_id"]), str(record["municipal_id"]))
        if key in seen_pairs:
            report["duplicate_pairs"] += 1
            report["problems"].append(f"line {line_no}: duplicate pair {key}")
            continue
        seen_pairs.add(key)

        records.append(record)
        report["valid_records"] += 1

        if record["review_status"] == "verified":
            report["verified_count"] += 1
            label = record["label"]
            report["label_distribution"][label] = (
                report["label_distribution"].get(label, 0) + 1
            )
        else:
            report["uncertain_count"] += 1
        regions.add(str(record["region"]))

    report["regions"] = sorted(regions)
    return records, report


def verified_training_records(records: list[dict]) -> list[dict]:
    """Filter to verified records with usable labels (REVIEW excluded)."""
    return [
        r
        for r in records
        if r["review_status"] == "verified" and r["label"] in (
            "MATCH", "MINOR_DISCREPANCY", "MAJOR_DISCREPANCY", "UNMATCHED",
        )
    ]


if __name__ == "__main__":
    records, rep = load_labels()
    print(json.dumps(rep, indent=2))
    sys.exit(0)
