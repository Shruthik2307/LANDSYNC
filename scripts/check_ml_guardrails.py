"""
scripts/check_ml_guardrails.py
==============================
CI model guardrails (spec §23). Exits non-zero (CI fails) if:

  1. Production code (backend/, engine/) references synthetic fixture
     files in a *runtime* code path (comments are ignored),
  2. A model artifact exists but is corrupt, single-class, or its
     feature schema does not match the served code,
  3. Training data referenced by training metadata is under data/sample
     or contract/mock,
  4. eval_accuracy.py-style fabricated evaluation patterns are detected
     (accuracy printed from random/synthetic generators).

Run in CI after the backend test job.
"""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

RUNTIME_DIRS = ("backend", "engine")
RUNTIME_EXTS = (".py",)

# Fixture references that must not appear in runtime code lines (comments
# stripped first). The demo gate itself (DEMO_FIXTURE_MODE handling) is
# allowed to *mention* the paths in strings guarded by the flag — we check
# for imports/reads instead, which are the actual runtime access.
FORBIDDEN_RUNTIME_PATTERNS = [
    (r"open\s*\(\s*['\"]data/sample/", "runtime code reads data/sample fixtures"),
    (r"open\s*\(\s*['\"]contract/mock/", "runtime code reads contract/mock fixtures"),
    (r"gpd\.read_file\(\s*['\"]data/sample/", "engine reads sample fixtures directly"),
    (r"json\.load\s*\(\s*open\s*\(\s*['\"]data/sample/", "engine loads sample fixtures directly"),
]

FABRICATION_PATTERNS = [
    (r"np\.random\.(uniform|rand|randint|choice)\([^)]*\).*\n.*accuracy", "accuracy derived from random data"),
    (r"random\.(uniform|randint)\([^)]*\).*\n.*accuracy", "accuracy derived from random data"),
]


def strip_comments(source: str) -> str:
    lines = []
    for line in source.splitlines():
        # crude but effective: drop everything after an unquoted #
        if "#" in line:
            idx = line.index("#")
            if "\"" not in line[:idx] and "'" not in line[:idx]:
                line = line[:idx]
        lines.append(line)
    return "\n".join(lines)


def check_runtime_fixture_references() -> list[str]:
    failures = []
    for d in RUNTIME_DIRS:
        base = ROOT / d
        if not base.exists():
            continue
        for path in base.rglob("*.py"):
            if "__pycache__" in path.parts or "tests" in path.parts:
                continue
            try:
                src = strip_comments(path.read_text(encoding="utf-8"))
            except Exception:
                continue
            for pattern, reason in FORBIDDEN_RUNTIME_PATTERNS:
                if re.search(pattern, src):
                    rel = path.relative_to(ROOT)
                    failures.append(f"{rel}: {reason}")
    return failures


def check_artifact() -> list[str]:
    failures = []
    artifact_path = ROOT / "models" / "reconciliation_model.json"
    if not artifact_path.exists():
        print("  model artifact: absent (MODEL_UNAVAILABLE is the honest state) — OK")
        return failures
    try:
        with open(artifact_path, "r", encoding="utf-8") as f:
            artifact = json.load(f)
    except json.JSONDecodeError as exc:
        return [f"models/reconciliation_model.json: corrupt artifact ({exc})"]

    sys.path.insert(0, str(ROOT))
    from engine.ml_schema import FEATURE_SCHEMA_VERSION

    if artifact.get("feature_schema_version") != FEATURE_SCHEMA_VERSION:
        failures.append(
            f"model artifact feature_schema_version mismatch: "
            f"{artifact.get('feature_schema_version')} vs code {FEATURE_SCHEMA_VERSION}"
        )
    dist = artifact.get("training_class_distribution") or {}
    if len(dist) < 2:
        failures.append("model artifact trained on a single class (constant predictor)")
    test = artifact.get("test_metrics") or {}
    if not (test.get("accuracy") or test.get("f1_macro")):
        failures.append("model artifact lacks held-out test metrics")
    else:
        print(
            f"  model artifact: {artifact.get('model_version')} "
            f"({artifact.get('model_type')}), held-out F1(macro)="
            f"{test.get('f1_macro')}"
        )
    return failures


def check_label_store() -> list[str]:
    """Validate data/verified/labels.jsonl: schema, synthetic markers, dupes."""
    failures = []
    labels_path = ROOT / "data" / "verified" / "labels.jsonl"
    if not labels_path.exists():
        print("  label store: absent (INSUFFICIENT_VERIFIED_DATA is honest) — OK")
        return failures
    sys.path.insert(0, str(ROOT))
    from scripts.label_store import load_labels

    records, rep = load_labels()
    if rep["invalid_records"]:
        failures.append(
            f"labels.jsonl: {rep['invalid_records']} invalid record(s) — "
            + "; ".join(rep["problems"][:5])
        )
    if rep["duplicate_pairs"]:
        failures.append(f"labels.jsonl: {rep['duplicate_pairs']} duplicate pair(s)")
    # Verified records must carry genuine provenance (a reviewer + source).
    for r in records:
        if r["review_status"] == "verified" and not str(r.get("evidence_source", "")).strip():
            failures.append(
                f"labels.jsonl: verified record {r.get('cadastral_id')!r} lacks evidence_source"
            )
            break
    print(
        f"  label store: {rep['verified_count']} verified "
        f"({rep.get('label_distribution', {})})"
    )
    return failures


def check_training_provenance() -> list[str]:
    failures = []
    meta_path = ROOT / "models" / "training_metadata.json"
    if not meta_path.exists():
        return failures
    try:
        with open(meta_path, "r", encoding="utf-8") as f:
            meta = json.load(f)
    except json.JSONDecodeError:
        return ["models/training_metadata.json: corrupt"]
    labels_path = str(meta.get("labels_path", "")).lower()
    if any(marker in labels_path for marker in ("sample", "mock", "fixture", "synthetic")):
        failures.append(
            f"training metadata references synthetic data: {labels_path!r} "
            "(production models must train on human-verified real labels only)"
        )
    return failures


def check_fabrication_patterns() -> list[str]:
    """Flag accuracy-from-random-data patterns in eval/training scripts."""
    failures = []
    for script in ("eval_accuracy.py", "scripts/train_model.py"):
        path = ROOT / script
        if not path.exists():
            continue
        src = path.read_text(encoding="utf-8")
        for pattern, reason in FABRICATION_PATTERNS:
            if re.search(pattern, src, re.MULTILINE):
                failures.append(f"{script}: {reason}")
    return failures


def main() -> int:
    print("== ML guardrails ==")
    failures: list[str] = []
    failures += check_runtime_fixture_references()
    failures += check_artifact()
    failures += check_label_store()
    failures += check_training_provenance()
    failures += check_fabrication_patterns()

    if failures:
        print("\nML GUARDRAIL FAILURES:")
        for f in failures:
            print(f"  ✗ {f}")
        return 1
    print("ML guardrails: OK")
    return 0


if __name__ == "__main__":
    sys.exit(main())
