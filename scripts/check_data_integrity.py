"""
CI data-integrity guard for the canonical LANDSYNC parcel dataset.

Prevents the "same parcel everywhere" bug from returning. Run standalone:

    python scripts/check_data_integrity.py            # file-based (fast, no deps)
    python scripts/check_data_integrity.py --api URL  # live deployment check
"""
from __future__ import annotations

import argparse
import json
import math
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
CADASTRAL = PROJECT_ROOT / "data" / "sample" / "cadastral.geojson"
MUNICIPAL = PROJECT_ROOT / "data" / "sample" / "municipal.geojson"
DEMO_FIXTURE = PROJECT_ROOT / "contract" / "mock" / "parcels.json"

# Plausible region for the canonical Hyderabad sample dataset (lng, lat).
BOUNDS = (78.0, 17.0, 79.0, 18.0)
VALID_PRIORITIES = {"HIGH", "MEDIUM", "LOW"}


def _fail(problems: list[str], msg: str) -> None:
    problems.append(msg)


def check_source_files(problems: list[str]) -> None:
    """Uniqueness / geometry / plausibility of the two canonical sources."""
    for path in (CADASTRAL, MUNICIPAL):
        if not path.exists():
            _fail(problems, f"canonical source missing: {path}")
            continue
        data = json.loads(path.read_text(encoding="utf-8"))
        feats = data.get("features", [])
        if not feats:
            _fail(problems, f"{path.name}: no features")
            continue
        ids = [f.get("properties", {}).get("parcel_id") for f in feats]
        if any(i is None for i in ids):
            _fail(problems, f"{path.name}: feature without parcel_id")
        dupes = {i for i in ids if ids.count(i) > 1}
        if dupes:
            _fail(problems, f"{path.name}: duplicate parcel_id values {sorted(dupes)}")
        rings = [json.dumps(f.get("geometry", {}).get("coordinates")) for f in feats]
        if len(set(rings)) != len(rings):
            _fail(problems, f"{path.name}: two features share identical geometry")
        for f, pid in zip(feats, ids):
            geom = f.get("geometry") or {}
            coords = geom.get("coordinates")
            if geom.get("type") != "Polygon" or not isinstance(coords, list) or not coords:
                _fail(problems, f"{path.name}: {pid}: not a Polygon with rings")
                continue
            ring = coords[0]
            if len(ring) < 4:
                _fail(problems, f"{path.name}: {pid}: ring has <4 points")
            if ring and ring[0] != ring[-1]:
                _fail(problems, f"{path.name}: {pid}: ring is not closed")
            for lng, lat in ring:
                if not (BOUNDS[0] < lng < BOUNDS[2] and BOUNDS[1] < lat < BOUNDS[3]):
                    _fail(problems, f"{path.name}: {pid}: coordinate ({lng}, {lat}) outside plausible bounds")
                    break


def check_reconciled(parcels: list[dict], problems: list[str]) -> None:
    """Full invariants on the reconciled parcel list (the API contract)."""
    if len(parcels) != 25:
        _fail(problems, f"expected 25 reconciled parcels, got {len(parcels)}")
    ids = [p.get("parcel_id") for p in parcels]
    if len(set(ids)) != len(ids):
        _fail(problems, f"duplicate parcel_id in reconciled output: {[i for i in ids if ids.count(i) > 1]}")
    for p in parcels:
        pid = p.get("parcel_id", "?")
        conf = p.get("confidence")
        if not isinstance(conf, (int, float)) or isinstance(conf, bool) or not (0 <= conf <= 100):
            _fail(problems, f"{pid}: confidence {conf!r} not in [0, 100]")
        if p.get("priority") not in VALID_PRIORITIES:
            _fail(problems, f"{pid}: invalid priority {p.get('priority')!r}")
        boundaries = p.get("boundaries") or {}
        cad = boundaries.get("cadastral") or {}
        ring = (cad.get("coordinates") or [[None]])[0]
        if len(ring) < 4 or ring[0] != ring[-1]:
            _fail(problems, f"{pid}: cadastral boundary missing/invalid")
        if "drone_ori" not in boundaries:
            _fail(problems, f"{pid}: missing drone_ori (municipal) boundary")
        rec = p.get("recommendation")
        if not isinstance(rec, str) or not rec.strip():
            _fail(problems, f"{pid}: empty recommendation")
    # Anti-degenerate guard: distinct parcels must not all be identical.
    confs = {p.get("confidence") for p in parcels}
    if len(parcels) > 1 and len(confs) < 3:
        _fail(problems, f"confidence values are near-constant ({sorted(confs)}) — degenerate scoring is back")
    rings = {json.dumps(p.get("boundaries", {}).get("cadastral", {}).get("coordinates")) for p in parcels}
    if len(rings) != len(parcels):
        _fail(problems, "two parcels share identical cadastral geometry in reconciled output")


def check_conflicts(parcels: list[dict], conflicts: list[dict], problems: list[str]) -> None:
    """Conflicts endpoint must match the flag-derived conflict set, uniquely."""
    cids = [c.get("parcel_id") for c in conflicts]
    if len(cids) != len(set(cids)):
        _fail(problems, "conflicts endpoint contains duplicate parcel_id values")
    expected = {
        p["parcel_id"]
        for p in parcels
        if p.get("geometry_conflict") or p.get("attribute_conflict") or p.get("duplicate_id")
    }
    if set(cids) != expected:
        _fail(problems, f"conflicts endpoint mismatch: extra={sorted(set(cids) - expected)} missing={sorted(expected - set(cids))}")


def check_demo_fixture(problems: list[str]) -> None:
    """The offline demo fixture must satisfy the same contract as the live API:
    every parcel carries BOTH source boundaries, and identical rings only
    occur where geometry_conflict is false (geometry-consensus parcels)."""
    if not DEMO_FIXTURE.exists():
        _fail(problems, f"demo fixture missing: {DEMO_FIXTURE}")
        return
    parcels = json.loads(DEMO_FIXTURE.read_text(encoding="utf-8"))
    if not parcels:
        _fail(problems, "demo fixture: no parcels")
        return
    ids = [p.get("parcel_id") for p in parcels]
    if len(set(ids)) != len(ids):
        _fail(problems, f"demo fixture: duplicate parcel_id: {[i for i in ids if ids.count(i) > 1]}")
    for p in parcels:
        pid = p.get("parcel_id", "?")
        boundaries = p.get("boundaries") or {}
        cad = (boundaries.get("cadastral") or {}).get("coordinates") or [[None]]
        if len(cad[0]) < 4 or cad[0][0] != cad[0][-1]:
            _fail(problems, f"demo fixture: {pid}: cadastral ring missing/unclosed")
        mun = boundaries.get("drone_ori")
        if not mun or not mun.get("coordinates"):
            _fail(problems, f"demo fixture: {pid}: missing drone_ori (municipal) boundary")
            continue
        if p.get("geometry_conflict") is False:
            if mun.get("coordinates") != (boundaries.get("cadastral") or {}).get("coordinates"):
                _fail(problems, f"demo fixture: {pid}: geometry_conflict=false but rings differ")
        conf = p.get("confidence")
        if not isinstance(conf, (int, float)) or isinstance(conf, bool) or not (0 <= conf <= 100):
            _fail(problems, f"demo fixture: {pid}: confidence {conf!r} not in [0, 100]")
        if p.get("priority") not in VALID_PRIORITIES:
            _fail(problems, f"demo fixture: {pid}: invalid priority {p.get('priority')!r}")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--api", type=str, default=None, help="base URL of a live deployment to also verify")
    args = parser.parse_args()

    problems: list[str] = []
    check_source_files(problems)
    check_demo_fixture(problems)

    # Reconcile locally when the backend stack is available; otherwise rely on --api.
    parcels: list[dict] = []
    try:
        backend_dir = PROJECT_ROOT / "backend"
        sys.path.insert(0, str(backend_dir))
        sys.path.insert(0, str(PROJECT_ROOT))
        from services.landsync_service import get_all_parcels, get_conflicts, load_data  # noqa: E402

        load_data(force_reload=True)
        parcels = get_all_parcels()
        check_reconciled(parcels, problems)
        check_conflicts(parcels, get_conflicts(), problems)
    except ImportError:
        print("note: backend deps unavailable — reconciled-output checks need --api or the backend venv")
    except Exception as exc:  # engine failure is itself a CI failure
        _fail(problems, f"engine reconciliation crashed: {exc}")

    if args.api:
        import urllib.request

        base = args.api.rstrip("/")
        with urllib.request.urlopen(f"{base}/api/parcels", timeout=30) as r:
            api_parcels = json.load(r)
        with urllib.request.urlopen(f"{base}/api/conflicts", timeout=30) as r:
            api_conflicts = json.load(r)
        check_reconciled(api_parcels, problems)
        check_conflicts(api_parcels, api_conflicts, problems)
        for p in api_parcels:
            with urllib.request.urlopen(f"{base}/api/parcels/{p['parcel_id']}", timeout=30) as r:
                one = json.load(r)
            if json.dumps(one, sort_keys=True) != json.dumps(p, sort_keys=True):
                _fail(problems, f"{p['parcel_id']}: /api/parcels/{{id}} disagrees with the list endpoint")
        if parcels and [p["parcel_id"] for p in sorted(parcels, key=lambda x: x["parcel_id"])] != [
            p["parcel_id"] for p in sorted(api_parcels, key=lambda x: x["parcel_id"])
        ]:
            _fail(problems, "local engine output and live API return different parcel ID sets")

    if problems:
        print("DATA INTEGRITY: FAIL")
        for p in problems:
            print(f"  - {p}")
        return 1
    print(f"DATA INTEGRITY: OK ({len(parcels) or 'api'} parcels verified)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
