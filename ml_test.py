import numpy as np
from backend.services.ml_service import conflict_detector, topology_validator
from shapely.geometry import Polygon

def test_ml():
    print("--- Testing ML Conflict Detector ---")
    sample_parcel = {
        'area_difference': 15.5,
        'iou_score': 0.85,
        'centroid_distance': 2.1,
        'vertex_count_diff': 2,
        'perimeter_ratio': 1.05,
        'geometry_conflict': True,
        'topology_valid': True,
        'attribute_mismatch_count': 1,
        'duplicate_id': False
    }
    try:
        has_conflict, confidence = conflict_detector.predict_conflict(sample_parcel)
        print(f"Prediction: has_conflict={has_conflict}, confidence={confidence:.2f}")
    except Exception as e:
        print(f"ML Prediction failed: {e}")

def test_topology():
    print("\n--- Testing Topology Validator ---")
    poly_valid = Polygon([(0,0), (0,1), (1,1), (1,0)])
    poly_invalid = Polygon([(0,0), (1,1), (0,1), (1,0)])
    res_valid = topology_validator.validate_topology(poly_valid)
    res_invalid = topology_validator.validate_topology(poly_invalid)
    print(f"Valid Poly -> is_valid: {res_valid['is_valid']}")
    print(f"Invalid Poly -> is_valid: {res_invalid['is_valid']}")

if __name__ == "__main__":
    test_ml()
    test_topology()
