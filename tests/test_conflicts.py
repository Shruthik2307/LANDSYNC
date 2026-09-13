import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from shapely.geometry import box
from engine.conflicts import evaluate_conflicts, _assign_priority


def test_normal_matching_parcel():
    geometry = box(0, 0, 10, 10)

    row = {
        "parcel_id": "TEST001",
        "geometry_a": geometry,
        "geometry_b": geometry,
        "area_m2_a": 100.0,
        "area_m2_b": 100.0,
        "land_use_a": "Residential",
        "land_use_b": "Residential",
    }

    result = evaluate_conflicts(row)

    assert result["parcel_id"] == "TEST001"
    assert result["geometry_conflict"] is False
    assert result["attribute_conflict"] is False
    assert result["confidence"] >= 90
    assert result["priority"] == "LOW"


def test_attribute_conflict():
    geometry = box(0, 0, 10, 10)

    row = {
        "parcel_id": "TEST002",
        "geometry_a": geometry,
        "geometry_b": geometry,
        "area_m2_a": 100.0,
        "area_m2_b": 100.0,
        "land_use_a": "Residential",
        "land_use_b": "Agricultural",
    }

    result = evaluate_conflicts(row)

    assert result["parcel_id"] == "TEST002"
    assert result["geometry_conflict"] is False
    assert result["attribute_conflict"] is True


def test_geometry_conflict():
    geometry_a = box(0, 0, 10, 10)
    geometry_b = box(5, 5, 15, 15)

    row = {
        "parcel_id": "TEST003",
        "geometry_a": geometry_a,
        "geometry_b": geometry_b,
        "area_m2_a": 100.0,
        "area_m2_b": 100.0,
        "land_use_a": "Residential",
        "land_use_b": "Residential",
    }

    result = evaluate_conflicts(row)

    assert result["parcel_id"] == "TEST003"
    assert result["geometry_conflict"] is True


def test_geometry_and_attribute_conflict():
    geometry_a = box(0, 0, 10, 10)
    geometry_b = box(5, 5, 15, 15)

    row = {
        "parcel_id": "TEST004",
        "geometry_a": geometry_a,
        "geometry_b": geometry_b,
        "area_m2_a": 100.0,
        "area_m2_b": 100.0,
        "land_use_a": "Residential",
        "land_use_b": "Agricultural",
    }

    result = evaluate_conflicts(row)

    assert result["parcel_id"] == "TEST004"
    assert result["geometry_conflict"] is True
    assert result["attribute_conflict"] is True


def test_confidence_score_perfect_match():
    geometry = box(0, 0, 10, 10)

    row = {
        "parcel_id": "TEST005",
        "geometry_a": geometry,
        "geometry_b": geometry,
        "area_m2_a": 100.0,
        "area_m2_b": 100.0,
        "land_use_a": "Residential",
        "land_use_b": "Residential",
    }

    result = evaluate_conflicts(row)

    assert result["confidence"] == 100
    assert result["priority"] == "LOW"


def test_priority_levels():
    assert _assign_priority(90) == "LOW"
    assert _assign_priority(70) == "MEDIUM"
    assert _assign_priority(40) == "HIGH"
def test_area_difference_reduces_confidence():
    geometry_a = box(0, 0, 10, 10)
    geometry_b = box(0, 0, 10, 9)

    row = {
        "parcel_id": "TEST006",
        "geometry_a": geometry_a,
        "geometry_b": geometry_b,
        "area_m2_a": 100.0,
        "area_m2_b": 90.0,
        "land_use_a": "Residential",
        "land_use_b": "Residential",
    }

    result = evaluate_conflicts(row)

    assert result["parcel_id"] == "TEST006"
    assert result["confidence"] < 100