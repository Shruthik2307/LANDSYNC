"""
scripts/label_expert_cli.py
===========================
Interactive Human-in-the-Loop Expert Labeling Tool for Real TGRAC Parcel Pairs.

Allows a human domain expert (surveyor / GIS officer) to review real geometric
and attribute discrepancies between TGRAC Cadastral and Municipal records and assign
verified ground-truth conflict labels:

  0 = No Conflict / Match (MATCH)
  1 = Minor Discrepancy (MINOR_DISCREPANCY)
  2 = Major/Critical Discrepancy (MAJOR_DISCREPANCY)

Requirements implemented:
  - Show both parcel geometries visually (2D terminal ASCII footprint overlay)
  - Show important spatial metrics (IoU, area ratio, centroid dist, hausdorff, etc.)
  - Show source/layer/provenance information
  - Allow reviewer to assign a label (0, 1, 2)
  - Allow skip (s)
  - Allow save/resume (skips already verified pairs)
  - Store reviewer, timestamp, source IDs and label
  - Never generate labels automatically from GIS scores
  - Never use demo/synthetic data
  - Support targeted balanced labeling across all 3 classes (--target-balanced)
  - Dataset statistics reporting (--stats)

Usage:
  python scripts/label_expert_cli.py --reviewer "Officer_Name"
  python scripts/label_expert_cli.py --reviewer "Officer_Name" --target-balanced
  python scripts/label_expert_cli.py --stats
"""
from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
backend_path = ROOT / "backend"
if str(backend_path) not in sys.path:
    sys.path.insert(0, str(backend_path))

from shapely.geometry import Point, Polygon, MultiPolygon, shape
from backend.services.label_store import SCHEMA_VERSION, append_label, load_labels
from scripts.dataset_stats import get_dataset_statistics, print_dataset_statistics

UNREVIEWED_FILE = ROOT / "data" / "unreviewed" / "tgrac_pairs.jsonl"
VERIFIED_FILE = ROOT / "data" / "verified" / "labels.jsonl"

LABEL_MAPPING = {
    "0": "MATCH",
    "1": "MINOR_DISCREPANCY",
    "2": "MAJOR_DISCREPANCY",
    "m": "MATCH",
    "match": "MATCH",
    "minor": "MINOR_DISCREPANCY",
    "major": "MAJOR_DISCREPANCY",
}

# ANSI color codes for rich terminal display
CYAN = "\033[96m"
YELLOW = "\033[93m"
GREEN = "\033[92m"
BOLD = "\033[1m"
DIM = "\033[2m"
RESET = "\033[0m"


def load_unreviewed_pairs() -> list[dict]:
    if not UNREVIEWED_FILE.exists():
        print(f"No unreviewed pairs found at {UNREVIEWED_FILE}.")
        print("Run `python scripts/collect_real_tgrac_pairs.py` first to harvest real pairs from TGRAC.")
        return []

    pairs = []
    with open(UNREVIEWED_FILE, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                pairs.append(json.loads(line))
    return pairs


def get_already_labeled_keys() -> set[str]:
    records, _ = load_labels(VERIFIED_FILE)
    return {f"{r['cadastral_id']}::{r['municipal_id']}" for r in records}


def render_ascii_overlay(boundaries: dict, width: int = 46, height: int = 12) -> str:
    """Render a 2D ASCII visual footprint overlay of Cadastral vs Municipal boundaries."""
    cad_raw = boundaries.get("cadastral")
    mun_raw = boundaries.get("municipal")

    if not cad_raw or not mun_raw:
        return "  [No geometry coordinates available for visual rendering]"

    try:
        p1 = shape(cad_raw)
        p2 = shape(mun_raw)
    except Exception as exc:
        return f"  [Failed parsing geometry for visual overlay: {exc}]"

    if p1.is_empty or p2.is_empty:
        return "  [Empty geometry]"

    # Calculate union bounding box
    minx1, miny1, maxx1, maxy1 = p1.bounds
    minx2, miny2, maxx2, maxy2 = p2.bounds
    minx = min(minx1, minx2)
    miny = min(miny1, miny2)
    maxx = max(maxx1, maxx2)
    maxy = max(maxy1, maxy2)

    dx = maxx - minx if (maxx - minx) > 1e-9 else 1e-9
    dy = maxy - miny if (maxy - miny) > 1e-9 else 1e-9

    # Add slight margin
    minx -= dx * 0.05
    maxx += dx * 0.05
    miny -= dy * 0.05
    maxy += dy * 0.05
    dx = maxx - minx
    dy = maxy - miny

    grid_lines = []
    # Top border
    grid_lines.append(f"  +{'-' * width}+")

    for r in range(height - 1, -1, -1):
        y = miny + (r / (height - 1)) * dy
        row_chars = []
        for c in range(width):
            x = minx + (c / (width - 1)) * dx
            pt = Point(x, y)
            in1 = p1.contains(pt) or p1.boundary.distance(pt) < (dx / width) * 0.4
            in2 = p2.contains(pt) or p2.boundary.distance(pt) < (dx / width) * 0.4

            if in1 and in2:
                # Overlap / intersection
                row_chars.append(f"{GREEN}#{RESET}")
            elif in1:
                # Cadastral only
                row_chars.append(f"{CYAN}C{RESET}")
            elif in2:
                # Municipal only
                row_chars.append(f"{YELLOW}M{RESET}")
            else:
                row_chars.append(f"{DIM}·{RESET}")
        grid_lines.append("  |" + "".join(row_chars) + "|")

    grid_lines.append(f"  +{'-' * width}+")
    grid_lines.append(f"  {CYAN}C = Cadastral (TGRAC L0){RESET} | {YELLOW}M = Municipal (TGRAC L1){RESET} | {GREEN}# = Overlap{RESET}")
    return "\n".join(grid_lines)


def sort_for_balanced_targeting(unlabeled_pairs: list[dict]) -> list[dict]:
    """Group pairs into likely metric bands so the reviewer can label balanced classes.

    Candidate bands (heuristic grouping for review queue ordering ONLY; reviewer makes final call):
      - Class 0 candidates: high IoU (>= 0.85)
      - Class 1 candidates: moderate IoU (0.35 <= IoU < 0.85) or moderate boundary displacement
      - Class 2 candidates: low IoU (< 0.35) or large area ratio mismatch
    Interleaves pairs from all 3 bands to achieve balanced review flow.
    """
    band_0 = []
    band_1 = []
    band_2 = []

    for p in unlabeled_pairs:
        iou = p.get("spatial_metrics", {}).get("iou", 0.0)
        ratio = p.get("spatial_metrics", {}).get("area_ratio", 1.0)
        if iou >= 0.85 and 0.8 <= ratio <= 1.25:
            band_0.append(p)
        elif 0.30 <= iou < 0.85:
            band_1.append(p)
        else:
            band_2.append(p)

    interleaved = []
    max_len = max(len(band_0), len(band_1), len(band_2), 1)
    for idx in range(max_len):
        if idx < len(band_0):
            interleaved.append(band_0[idx])
        if idx < len(band_1):
            interleaved.append(band_1[idx])
        if idx < len(band_2):
            interleaved.append(band_2[idx])

    return interleaved


def run_interactive_labeling(
    reviewer_name: str,
    limit: Optional[int] = None,
    target_balanced: bool = False,
    filter_class: Optional[str] = None,
):
    pairs = load_unreviewed_pairs()
    if not pairs:
        return

    already_labeled = get_already_labeled_keys()
    unlabeled = [p for p in pairs if f"{p['cadastral_id']}::{p['municipal_id']}" not in already_labeled]

    if filter_class:
        if filter_class == "0":
            unlabeled = [p for p in unlabeled if p.get("spatial_metrics", {}).get("iou", 0) >= 0.80]
        elif filter_class == "1":
            unlabeled = [p for p in unlabeled if 0.30 <= p.get("spatial_metrics", {}).get("iou", 0) < 0.80]
        elif filter_class == "2":
            unlabeled = [p for p in unlabeled if p.get("spatial_metrics", {}).get("iou", 0) < 0.30]

    if target_balanced:
        unlabeled = sort_for_balanced_targeting(unlabeled)

    stats = get_dataset_statistics()

    print("=" * 72)
    print(f"{BOLD}LANDSYNC — REAL GEOSPATIAL EXPERT GROUND-TRUTH LABELING WORKFLOW{RESET}")
    print("=" * 72)
    print(f"Reviewer         : {reviewer_name}")
    print(f"Harvested Pool   : {len(pairs):,} pairs")
    print(f"Already Verified : {len(already_labeled):,} pairs")
    print(f"Remaining Queue  : {len(unlabeled):,} pairs")
    print(
        f"Current Balance  : Class 0: {stats['class_0_count']} | "
        f"Class 1: {stats['class_1_count']} | Class 2: {stats['class_2_count']}"
    )
    print("=" * 72)

    if not unlabeled:
        print("All candidate pairs have already been reviewed and verified!")
        return

    labeled_in_session = 0
    for i, pair in enumerate(unlabeled):
        if limit is not None and labeled_in_session >= limit:
            print(f"\nReached session limit of {limit} parcels.")
            break

        sm = pair.get("spatial_metrics", {})
        am = pair.get("attribute_metrics", {})
        cad_id = pair["cadastral_id"]
        mun_id = pair["municipal_id"]
        region = pair.get("region", "Telangana")
        prov = pair.get("provenance", {})
        boundaries = pair.get("boundaries", {})

        print(f"\n{BOLD}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━{RESET}")
        print(f"{BOLD}[Pair {i + 1}/{len(unlabeled)}] Cadastral: {CYAN}{cad_id}{RESET}  vs  Municipal: {YELLOW}{mun_id}{RESET}")
        print(f"  Region       : {region} (bbox: {pair.get('bbox', 'N/A')})")
        print(f"  Provenance   : {prov.get('cadastral_layer', 'Cadastral L0')} vs {prov.get('municipal_layer', 'ULB L1')}")
        print(f"  Collected At : {pair.get('collected_at', 'N/A')}")
        print("-" * 72)

        # 1. Visual Geometry Display
        print(f"{BOLD}Visual 2D Parcel Footprint:{RESET}")
        print(render_ascii_overlay(boundaries, width=46, height=10))
        print("-" * 72)

        # 2. Spatial Metrics
        print(f"{BOLD}Key Spatial Metrics:{RESET}")
        print(
            f"  Spatial IoU            : {sm.get('iou', 0.0):.4f}           "
            f"| Shape Similarity      : {sm.get('shape_similarity', 0.0):.4f}"
        )
        print(
            f"  Area Ratio             : {sm.get('area_ratio', 0.0):.4f}           "
            f"| Area Difference       : {sm.get('area_difference_m2', 0.0):.1f} m²"
        )
        print(
            f"  Cadastral Area         : {sm.get('cadastral_area_m2', 0.0):.1f} m²       "
            f"| Municipal Area        : {sm.get('municipal_area_m2', 0.0):.1f} m²"
        )
        print(
            f"  Centroid Distance      : {sm.get('centroid_distance_m', 0.0):.2f} m         "
            f"| Hausdorff Distance    : {sm.get('hausdorff_distance_m', 0.0):.2f} m"
        )
        print(
            f"  Boundary Displacement  : {sm.get('boundary_displacement_m', 0.0):.2f} m         "
            f"| Compactness Diff      : {sm.get('compactness_difference', 0.0):.4f}"
        )
        print(
            f"  Overlap % of Cadastral : {sm.get('overlap_pct_of_cadastral', 0.0):.2f}%         "
            f"| Overlap % of Municipal: {sm.get('overlap_pct_of_municipal', 0.0):.2f}%"
        )
        print("-" * 72)

        # 3. Label prompt
        choice = ""
        while choice not in ("0", "1", "2", "s", "q", "m", "minor", "major"):
            print(f"{BOLD}Assign Genuine Ground-Truth Label:{RESET}")
            print(f"  [{GREEN}0{RESET}] MATCH                 (0 = No Conflict / Valid parcel match)")
            print(f"  [{YELLOW}1{RESET}] MINOR_DISCREPANCY     (1 = Minor discrepancy / surveying offset / edge sliver)")
            print(f"  [{CYAN}2{RESET}] MAJOR_DISCREPANCY     (2 = Critical conflict / significant overlap / encroachment)")
            print(f"  [{DIM}s{RESET}] Skip this parcel pair")
            print(f"  [{DIM}q{RESET}] Quit and save session progress")
            try:
                choice = input(f"{BOLD}Your expert label [0/1/2/s/q]: {RESET}").strip().lower()
            except (EOFError, KeyboardInterrupt):
                choice = "q"
                break

        if choice == "q":
            print(f"\nSession paused. Progress saved permanently to {VERIFIED_FILE}.")
            break
        elif choice == "s":
            print("Skipped pair.")
            continue

        selected_label = LABEL_MAPPING[choice]
        try:
            notes = input("Surveyor inspection notes (optional, press Enter to omit): ").strip()
        except (EOFError, KeyboardInterrupt):
            notes = ""

        # Permanent record with full audit provenance
        record = {
            "schema_version": SCHEMA_VERSION,
            "cadastral_id": cad_id,
            "municipal_id": mun_id,
            "region": region,
            "label": selected_label,
            "review_status": "verified",
            "reviewer": reviewer_name,
            "evidence_source": f"TGRAC_TELANGANA: {prov.get('cadastral_layer', 'Cadastral')} vs {prov.get('municipal_layer', 'Municipal')}",
            "pair_metrics": pair.get("pair_metrics", {}),
            "notes": notes or f"Ground truth verified by {reviewer_name} via expert CLI",
            "submitted_at": datetime.now(timezone.utc).isoformat(),
        }

        res = append_label(record, path=VERIFIED_FILE)
        if res["ok"]:
            labeled_in_session += 1
            print(f"{GREEN}✓ Successfully saved label '{selected_label}'{RESET}")
            # Show running balance
            curr_stats = get_dataset_statistics()
            print(
                f"  Running verified count: {curr_stats['total_reviewed']} "
                f"(Class 0: {curr_stats['class_0_count']} | Class 1: {curr_stats['class_1_count']} | Class 2: {curr_stats['class_2_count']})"
            )
        else:
            print(f"{YELLOW}✗ Label rejected by validation: {res.get('problems')}{RESET}")

    print("\n" + "=" * 72)
    print(f"Session finished: {labeled_in_session} labels added by {reviewer_name}.")
    print_dataset_statistics()


def batch_import_expert_labels(batch_file_path: Path, reviewer_name: str):
    """Import expert labels from an authenticated reviewer JSONL file."""
    if not batch_file_path.exists():
        print(f"Batch file {batch_file_path} not found.")
        return

    with open(batch_file_path, "r", encoding="utf-8") as f:
        data = [json.loads(line) for line in f if line.strip()]

    print(f"Importing {len(data)} expert labels from {batch_file_path}...")
    saved = 0
    for item in data:
        raw_label = str(item.get("label", "")).strip()
        label = LABEL_MAPPING.get(raw_label, raw_label)
        record = {
            "schema_version": SCHEMA_VERSION,
            "cadastral_id": item["cadastral_id"],
            "municipal_id": item["municipal_id"],
            "region": item.get("region", "Telangana"),
            "label": label,
            "review_status": "verified",
            "reviewer": item.get("reviewer") or reviewer_name,
            "evidence_source": item.get("evidence_source", "TGRAC_TELANGANA: Cadastral vs Municipal"),
            "pair_metrics": item["pair_metrics"],
            "notes": item.get("notes", "Expert human ground truth"),
            "submitted_at": datetime.now(timezone.utc).isoformat(),
        }
        res = append_label(record, path=VERIFIED_FILE)
        if res["ok"]:
            saved += 1
    print(f"Successfully verified and imported {saved}/{len(data)} labels into {VERIFIED_FILE}.")
    print_dataset_statistics()


def main():
    parser = argparse.ArgumentParser(description="LANDSYNC Real TGRAC Expert Labeling Tool")
    parser.add_argument("--reviewer", type=str, default="Senior GIS Officer (Telangana)", help="Name/designation of the human reviewer")
    parser.add_argument("--limit", type=int, default=None, help="Max pairs to review in this session")
    parser.add_argument("--target-balanced", action="store_true", help="Interleave candidates across metric bands to build balanced classes")
    parser.add_argument("--filter-class", type=str, choices=["0", "1", "2"], help="Filter queue to target candidates for a specific class")
    parser.add_argument("--import-file", type=str, default=None, help="Batch import expert labels from JSONL")
    parser.add_argument("--stats", action="store_true", help="Show current dataset review statistics and exit")
    args = parser.parse_args()

    if args.stats:
        print_dataset_statistics()
        return

    if args.import_file:
        batch_import_expert_labels(Path(args.import_file), args.reviewer)
    else:
        run_interactive_labeling(
            reviewer_name=args.reviewer,
            limit=args.limit,
            target_balanced=args.target_balanced,
            filter_class=args.filter_class,
        )


if __name__ == "__main__":
    main()
